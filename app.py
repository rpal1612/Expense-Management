import os
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
import psycopg2
from psycopg2 import extras, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. Database Configuration ---
# NOTE: Replace these placeholder values with your actual PostgreSQL credentials.
# It's best practice to use environment variables for production security.
DB_CONFIG = {
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "ExpenseFlow")
}

app = Flask(__name__)
# Enable CORS to allow the frontend (HTML file) to fetch from this API
CORS(app) 

# Base directory for serving static HTML files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file if present (makes local dev configuration easier)
env_path = Path(BASE_DIR) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    # refresh DB_CONFIG with any values from .env
    DB_CONFIG.update({
        'user': os.getenv('DB_USER', DB_CONFIG['user']),
        'password': os.getenv('DB_PASSWORD', DB_CONFIG['password']),
        'host': os.getenv('DB_HOST', DB_CONFIG['host']),
        'port': os.getenv('DB_PORT', DB_CONFIG['port']),
        'database': os.getenv('DB_NAME', DB_CONFIG['database'])
    })

def _masked_db_config():
    # Mask password when logging
    cfg = DB_CONFIG.copy()
    if cfg.get('password'):
        cfg['password'] = ''
    return cfg

def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    try:
        # Connect to PostgreSQL server (without specifying database)
        server_config = DB_CONFIG.copy()
        server_config['database'] = 'postgres'  # Connect to default postgres database
        
        conn = psycopg2.connect(**server_config)
        conn.autocommit = True  # Required for CREATE DATABASE
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_CONFIG['database'],))
        exists = cursor.fetchone()
        
        if not exists:
            # Create database
            cursor.execute(f'CREATE DATABASE "{DB_CONFIG["database"]}"')
            app.logger.info(f'Database "{DB_CONFIG["database"]}" created successfully.')
        else:
            app.logger.info(f'Database "{DB_CONFIG["database"]}" already exists.')
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        app.logger.error(f'Failed to create database: {e}')
        return False

def create_test_users():
    """Create test users if they don't exist."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if test users already exist
        cursor.execute("SELECT COUNT(*) FROM Users WHERE email LIKE '%@flow.com'")
        existing_users = cursor.fetchone()[0]
        
        if existing_users == 0:
            app.logger.info('Creating test users...')
            
            # Test users with hashed passwords
            test_users = [
                ('John Doe', 'john.admin@flow.com', 'admin123', 'Admin', True),
                ('Sarah Johnson', 'sarah.manager@flow.com', 'manager123', 'Manager', True),
                ('Mike Chen', 'mike.employee@flow.com', 'employee123', 'Employee', False),
                ('Emily Davis', 'emily.employee@flow.com', 'employee123', 'Employee', False)
            ]
            
            for full_name, email, password, role, is_manager_approver in test_users:
                password_hash = generate_password_hash(password)
                cursor.execute("""
                    INSERT INTO Users (company_id, full_name, email, password_hash, role, is_manager_approver)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (1, full_name, email, password_hash, role, is_manager_approver))
            
            # Set up manager relationships
            cursor.execute("""
                UPDATE Users 
                SET manager_id = (SELECT user_id FROM Users WHERE email = 'john.admin@flow.com')
                WHERE email = 'sarah.manager@flow.com'
            """)
            
            cursor.execute("""
                UPDATE Users 
                SET manager_id = (SELECT user_id FROM Users WHERE email = 'sarah.manager@flow.com')
                WHERE email IN ('mike.employee@flow.com', 'emily.employee@flow.com')
            """)
            
            conn.commit()
            app.logger.info('Test users created successfully.')
            app.logger.info('Test credentials:')
            app.logger.info('  Admin: john.admin@flow.com / admin123')
            app.logger.info('  Manager: sarah.manager@flow.com / manager123')
            app.logger.info('  Employee: mike.employee@flow.com / employee123')
            app.logger.info('  Employee: emily.employee@flow.com / employee123')
        else:
            app.logger.info('Test users already exist.')
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        app.logger.error(f'Failed to create test users: {e}')

def setup_database_schema():
    """Set up database tables if they don't exist."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if Users table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """)
        
        tables_exist = cursor.fetchone()[0]
        
        if not tables_exist:
            app.logger.info('Tables do not exist. Creating database schema...')
            
            # Read and execute the SQL schema
            schema_file = os.path.join(BASE_DIR, 'db.sql')
            if os.path.exists(schema_file):
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                # Execute the schema (split by semicolon for multiple statements)
                cursor.execute(schema_sql)
                conn.commit()
                app.logger.info('Database schema created successfully.')
                
                # Create test users after schema is set up
                cursor.close()
                conn.close()
                create_test_users()
            else:
                app.logger.warning('db.sql file not found. Please create tables manually.')
        else:
            app.logger.info('Database tables already exist.')
            # Still try to create test users if they don't exist
            cursor.close()
            conn.close()
            create_test_users()
            
        return True
        
    except Exception as e:
        app.logger.error(f'Failed to setup database schema: {e}')
        return False

def check_db_connection_once():
    """Try connecting once at startup and set up database if needed."""
    try:
        # First, try to create database if it doesn't exist
        if not create_database_if_not_exists():
            app.logger.error('Failed to create database. Please check PostgreSQL connection.')
            return
        
        # Then try to connect to the target database
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        app.logger.info('Database connection successful.')
        
        # Set up schema if needed
        setup_database_schema()
        
    except Exception as e:
        app.logger.error('Database connection failed at startup. DB_CONFIG (masked): %s', _masked_db_config())
        app.logger.error('Detailed error: %s', e)
        app.logger.error('Please ensure PostgreSQL is running and credentials are correct.')

# Run database setup at startup
try:
    check_db_connection_once()
except Exception:
    # Already logged inside function; do not crash the app so frontend can still be served.
    pass

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        app.logger.error(f"Database connection failed: {e}")
        # Re-raise the exception or return None, depending on error handling strategy
        raise ConnectionError("Could not connect to the database. Check DB_CONFIG and PostgreSQL service.") from e

# --- 2. Helper Functions ---

def execute_query(sql, params=None, fetch_mode='all'):
    """Helper function to execute SQL queries and handle connections/cursors."""
    conn = None
    try:
        conn = get_db_connection()
        # Use DictCursor to get results as dictionaries
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(sql, params)

        if sql.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            conn.commit()
            return {"success": True}
        
        if fetch_mode == 'one':
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
        
        # Convert psycopg2.extras.DictRow to a standard list of dictionaries
        if result is None:
            return None
            
        # Convert results to a list of standard dictionaries
        data = [dict(row) for row in result] if isinstance(result, list) else dict(result)

        return data

    except (Exception, psycopg2.Error) as error:
        app.logger.error(f"Error executing SQL: {error}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# --- 3. API Endpoints ---

@app.route('/api/manager/dashboard/<uuid:manager_id>', methods=['GET'])
def fetch_manager_dashboard_data(manager_id):
    """
    Fetches all data required for the Manager Dashboard, Approvals, and Team Expenses pages.
    """
    manager_id_str = str(manager_id)
    
    try:
        # SQL to get all relevant expenses for the manager's team
        sql_expenses = """
        SELECT
            e.expense_id,
            e.description,
            e.category,
            e.expense_date,
            e.converted_amount,
            e.status,
            e.current_approval_step,
            u.full_name AS user_name,
            u.user_id AS user_id
        FROM Expenses e
        JOIN Users u ON e.user_id = u.user_id
        -- Select expenses submitted by employees who report to this manager
        WHERE u.manager_id = %s
        ORDER BY e.expense_date DESC;
        """
        all_team_expenses = execute_query(sql_expenses, (manager_id_str,))
        
        if not all_team_expenses:
             all_team_expenses = []

        # Filter and calculate stats based on fetched data
        pending_approvals = [
            exp for exp in all_team_expenses
            if exp['status'] == 'Pending' and exp['current_approval_step'] == 1 # Manager is Step 1
        ]
        
        # Calculate YTD total spent by the team (converted amount)
        total_spent_ytd = sum(exp['converted_amount'] for exp in all_team_expenses)

        response_data = {
            "totalSpentYTD": float(total_spent_ytd),
            "pendingApprovals": pending_approvals,
            "allTeamExpenses": all_team_expenses
        }
        
        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Error fetching dashboard data: {e}")
        return jsonify({"message": "Failed to retrieve dashboard data.", "error": str(e)}), 500


# Serve the main index page
@app.route('/', methods=['GET'])
def index():
    # Serve the top-level index.html in the project root
    return send_from_directory(BASE_DIR, 'index.html')


# Serve static dashboard pages for roles (admin, manager, employee)
@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    return send_from_directory(os.path.join(BASE_DIR, 'admin'), 'admin_panel.html')


@app.route('/manager/dashboard', methods=['GET'])
def manager_dashboard():
    return send_from_directory(os.path.join(BASE_DIR, 'manager'), 'manager_dashboard.html')


@app.route('/employee/dashboard', methods=['GET'])
def employee_dashboard():
    return send_from_directory(os.path.join(BASE_DIR, 'employee'), 'employee_dashboard.html')


# --- Authentication endpoints (simple/login/register for demo) ---
@app.route('/api/auth/login', methods=['POST'])
def login():
    payload = request.get_json() or {}
    email = payload.get('email')
    password = payload.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required.'}), 400

    if not email or not password:
        return jsonify({'message': 'Email and password are required.'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        cursor.execute("SELECT user_id, full_name, role, password_hash FROM Users WHERE email = %s", (email,))
        user_row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user_row:
            return jsonify({'message': 'Invalid credentials.'}), 401

        # verify password hash
        stored_hash = user_row.get('password_hash')
        if not stored_hash or not check_password_hash(stored_hash, password):
            return jsonify({'message': 'Invalid credentials.'}), 401

        user = {
            'user_id': str(user_row.get('user_id')),
            'full_name': user_row.get('full_name'),
            'role': user_row.get('role')
        }

        role = (user.get('role') or '').lower()
        if role == 'admin':
            redirect_path = '/admin/dashboard'
        elif role == 'manager':
            redirect_path = '/manager/dashboard'
        else:
            redirect_path = '/employee/dashboard'

        return jsonify({'user': user, 'redirect': redirect_path}), 200

    except ConnectionError as e:
        app.logger.critical(f'Login DB connection failed: {e}')
        return jsonify({'message': 'Database connection error.'}), 500
    except Exception as e:
        app.logger.error(f'Login failed: {e}')
        return jsonify({'message': 'Internal server error during login.'}), 500


@app.route('/api/auth/register', methods=['POST'])
def register():
    payload = request.get_json() or {}
    full_name = payload.get('full_name')
    email = payload.get('email')
    password = payload.get('password')
    role = payload.get('role', 'employee')
    if not all([full_name, email, password]):
        return jsonify({'message': 'full_name, email and password are required.'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email exists
        cursor.execute("SELECT 1 FROM Users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'message': 'Email already registered.'}), 400

        # Hash the password before storing
        pw_hash = generate_password_hash(password)

        # Default company_id to 1 (seeded in db.sql)
        company_id = 1

        # Insert user using schema-compatible columns
        insert_sql = """
        INSERT INTO Users (company_id, full_name, email, password_hash, role, is_manager_approver)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING user_id
        """

        is_manager_approver = True if (role or '').lower() == 'manager' else False

        cursor.execute(insert_sql, (company_id, full_name, email, pw_hash, role.capitalize(), is_manager_approver))
        new_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({'message': 'User registered successfully.', 'user_id': str(new_id)}), 201

    except ConnectionError as ce:
        app.logger.critical(f'Registration DB connection failed: {ce}', exc_info=True)
        return jsonify({'message': 'Database connection error. Please check server configuration.'}), 500
    except IntegrityError as ie:
        app.logger.error(f'Registration integrity error: {ie}', exc_info=True)
        if conn:
            try: conn.rollback()
            except Exception: pass
        return jsonify({'message': 'Email already registered.'}), 400
    except Exception as e:
        app.logger.error(f'Registration failed: {e}', exc_info=True)
        if conn:
            try: conn.rollback()
            except Exception: pass
        return jsonify({'message': 'Internal server error during registration.', 'error': str(e) if app.debug else ''}), 500
    finally:
        if cursor:
            try: cursor.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass


@app.route('/api/expenses/process', methods=['POST'])
def process_approval():
    """
    Handles the approval or rejection of an expense, executing permanent DB changes.
    """
    try:
        payload = request.get_json()
        expense_id = payload.get('expenseId')
        action = payload.get('action') # 'Approve' or 'Reject'
        comments = payload.get('comments', '')
        approver_id = payload.get('approverId')

        if not all([expense_id, action, approver_id]):
            return jsonify({"message": "Missing required fields in payload."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start Transaction for atomicity (ensures both queries succeed or fail together)
        cursor.execute("BEGIN")

        # 1. Get the current expense status and step to log the transaction
        cursor.execute("SELECT status, current_approval_step FROM Expenses WHERE expense_id = %s", (expense_id,))
        current_expense = cursor.fetchone()
        
        if not current_expense:
            cursor.execute("ROLLBACK")
            return jsonify({"message": "Expense not found."}), 404

        current_step = current_expense[1]
        
        # --- 2. INSERT into ApprovalTransactions (Log the action) ---
        log_sql = """
        INSERT INTO ApprovalTransactions 
            (expense_id, approver_id, step_sequence, status, comments) 
        VALUES 
            (%s, %s, %s, %s, %s);
        """
        cursor.execute(log_sql, (expense_id, approver_id, current_step, action, comments))
        
        # --- 3. UPDATE Expenses (Change the overall state) ---
        if action == 'Approve':
            # For simplicity, we assume Step 2 is the final step in the current setup.
            # In a real app, logic would determine the NEXT status/step (e.g., 'Pending' step 2 or 'Approved').
            new_status = 'Pending' if current_step < 2 else 'Approved'
            new_step = current_step + 1
            
            update_sql = """
            UPDATE Expenses
            SET status = %s, current_approval_step = %s
            WHERE expense_id = %s;
            """
            cursor.execute(update_sql, (new_status, new_step, expense_id))
            
            final_status = new_status
            
        elif action == 'Reject':
            # Rejection is generally a terminal status, setting it to 'Rejected'.
            update_sql = """
            UPDATE Expenses
            SET status = 'Rejected'
            WHERE expense_id = %s;
            """
            cursor.execute(update_sql, ('Rejected', expense_id))
            final_status = 'Rejected'
        
        # Commit the transaction
        conn.commit()
        
        return jsonify({
            "message": f"Expense successfully {action}ed.",
            "newStatus": final_status,
            "expenseId": expense_id
        }), 200

    except ConnectionError as e:
        # Catch explicit connection errors raised by get_db_connection
        app.logger.critical(f"DB CONNECTION ERROR: {e}")
        return jsonify({"message": "Database connection error. Please check server configuration."}), 500
    except Exception as e:
        app.logger.error(f"Transaction failed: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"message": "Internal error during expense processing."}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Returns a basic health check including DB connectivity."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({'status': 'ok', 'db': 'connected'}), 200
    except Exception as e:
        app.logger.error('Health check DB error: %s', e)
        return jsonify({'status': 'degraded', 'db': 'unreachable', 'error': str(e)}), 503


if __name__ == '__main__':
    # Flask runs the server on http://localhost:3000
    app.run(host='0.0.0.0', port=3000, debug=True)