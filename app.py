import os
import json
import requests
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

def setup_company_data():
    """Ensure company data exists with hardcoded values"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Ensure the company record exists with hardcoded data
        cursor.execute("""
            INSERT INTO Companies (company_id, name, default_currency_code, created_at)
            VALUES (1, 'ExpenseFlow Corp', 'USD', CURRENT_TIMESTAMP)
            ON CONFLICT (company_id) 
            DO UPDATE SET 
                name = 'ExpenseFlow Corp'
            WHERE Companies.name IS NULL OR Companies.name = ''
        """)
        
        conn.commit()
        app.logger.info("Company data initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Error setting up company data: {e}")
    finally:
        cursor.close()
        conn.close()

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
                setup_company_data()
            else:
                app.logger.warning('db.sql file not found. Please create tables manually.')
        else:
            app.logger.info('Database tables already exist.')
            # Still try to create test users if they don't exist
            cursor.close()
            conn.close()
            create_test_users()
            
        # Always ensure company data is properly set up
        setup_company_data()
            
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

def get_exchange_rates(base_currency='USD'):
    """Get current exchange rates from the API"""
    try:
        response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{base_currency}', timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('rates', {})
        else:
            app.logger.error(f"Exchange rate API failed with status: {response.status_code}")
            return None
    except Exception as e:
        app.logger.error(f"Error fetching exchange rates: {e}")
        return None

def convert_currency_amount(amount, from_currency, to_currency):
    """Convert amount from one currency to another"""
    if from_currency == to_currency:
        return amount
    
    try:
        # Get exchange rates with from_currency as base
        rates = get_exchange_rates(from_currency)
        if not rates or to_currency not in rates:
            app.logger.error(f"Could not get exchange rate from {from_currency} to {to_currency}")
            return amount  # Return original amount if conversion fails
        
        converted_amount = amount * rates[to_currency]
        return round(converted_amount, 2)
    except Exception as e:
        app.logger.error(f"Currency conversion error: {e}")
        return amount  # Return original amount if conversion fails

def convert_all_expenses_to_new_currency(old_currency, new_currency):
    """Convert all existing expenses from old currency to new currency"""
    if old_currency == new_currency:
        return True
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Get all expenses that need conversion
        cursor.execute("""
            SELECT expense_id, amount, currency_code 
            FROM Expenses 
            WHERE currency_code = %s
        """, (old_currency,))
        
        expenses_to_convert = cursor.fetchall()
        
        if not expenses_to_convert:
            app.logger.info(f"No expenses found in {old_currency} to convert")
            return True
        
        app.logger.info(f"Converting {len(expenses_to_convert)} expenses from {old_currency} to {new_currency}")
        
        # Get exchange rate
        rates = get_exchange_rates(old_currency)
        if not rates or new_currency not in rates:
            app.logger.error(f"Could not get exchange rate from {old_currency} to {new_currency}")
            return False
        
        conversion_rate = rates[new_currency]
        converted_count = 0
        
        # Convert each expense
        for expense in expenses_to_convert:
            old_amount = float(expense['amount'])
            new_amount = round(old_amount * conversion_rate, 2)
            
            cursor.execute("""
                UPDATE Expenses 
                SET amount = %s, currency_code = %s 
                WHERE expense_id = %s
            """, (new_amount, new_currency, expense['expense_id']))
            
            converted_count += 1
        
        conn.commit()
        app.logger.info(f"Successfully converted {converted_count} expenses from {old_currency} to {new_currency}")
        return True
        
    except Exception as e:
        app.logger.error(f"Error converting expenses: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# Original helper functions continue below...

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
    return send_from_directory(os.path.join(BASE_DIR, 'admin'), 'admin_user_management.html')


@app.route('/admin/workflow', methods=['GET'])
def admin_workflow():
    return send_from_directory(os.path.join(BASE_DIR, 'admin'), 'approval_workflow.html')


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


# --- Admin User Management Endpoints ---

@app.route('/api/admin/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics for admin panel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Get total employees count
        cursor.execute("SELECT COUNT(*) as total_users FROM Users WHERE role != 'Admin'")
        user_stats = cursor.fetchone()
        total_employees = user_stats['total_users']
        
        # Get managers count
        cursor.execute("SELECT COUNT(*) as total_managers FROM Users WHERE role = 'Manager'")
        manager_stats = cursor.fetchone()
        total_managers = manager_stats['total_managers']
        
        # Get company default currency
        cursor.execute("SELECT default_currency_code, name FROM Companies LIMIT 1")
        company_info = cursor.fetchone()
        default_currency = company_info['default_currency_code'] if company_info else 'USD'
        company_name = company_info['name'] if company_info else 'ExpenseFlow'
        
        # Get total users count (all users)
        cursor.execute("SELECT COUNT(*) as total_all_users FROM Users")
        all_user_stats = cursor.fetchone()
        total_all_users = all_user_stats['total_all_users']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_employees': total_employees,
            'total_managers': total_managers,
            'total_all_users': total_all_users,
            'default_currency': default_currency,
            'company_name': company_name
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to get dashboard stats: {e}')
        return jsonify({'message': 'Failed to load dashboard statistics'}), 500


@app.route('/api/admin/currency', methods=['PUT'])
def update_company_currency():
    """Update company default currency and convert all existing expenses"""
    try:
        payload = request.get_json() or {}
        new_currency_code = payload.get('currency_code')
        
        if not new_currency_code:
            return jsonify({'message': 'Currency code is required'}), 400
        
        # Validate currency code (basic validation)
        valid_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'INR', 'CAD', 'AUD', 'CHF', 'CNY', 'SGD']
        if new_currency_code not in valid_currencies:
            return jsonify({'message': 'Invalid currency code'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Get current currency first
        cursor.execute("SELECT default_currency_code FROM Companies WHERE company_id = 1")
        current_company = cursor.fetchone()
        old_currency_code = current_company['default_currency_code'] if current_company else 'USD'
        
        # Check if currency is actually changing
        if old_currency_code == new_currency_code:
            cursor.close()
            conn.close()
            return jsonify({
                'message': f'Currency is already set to {new_currency_code}',
                'new_currency': new_currency_code
            }), 200
        
        # Update company currency first
        cursor.execute("""
            INSERT INTO Companies (company_id, name, default_currency_code, created_at)
            VALUES (1, 'ExpenseFlow Corp', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (company_id) 
            DO UPDATE SET 
                default_currency_code = EXCLUDED.default_currency_code,
                name = 'ExpenseFlow Corp'
        """, (new_currency_code,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'message': 'Failed to update company currency'}), 500
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Convert all existing expenses to new currency
        app.logger.info(f'Converting expenses from {old_currency_code} to {new_currency_code}')
        conversion_success = convert_all_expenses_to_new_currency(old_currency_code, new_currency_code)
        
        if not conversion_success:
            app.logger.warning(f'Currency updated but expense conversion failed from {old_currency_code} to {new_currency_code}')
            return jsonify({
                'message': f'Currency updated to {new_currency_code}, but some expenses could not be converted. Please check the logs.',
                'new_currency': new_currency_code,
                'conversion_warning': True
            }), 200
        
        app.logger.info(f'Company currency and expenses successfully updated to: {new_currency_code}')
        
        return jsonify({
            'message': f'Currency successfully updated to {new_currency_code}. All expenses have been converted.',
            'new_currency': new_currency_code,
            'expenses_converted': True
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to update currency: {e}')
        return jsonify({'message': 'Failed to update currency'}), 500


@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Get all users for admin management"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Get all users with their manager information
        cursor.execute("""
            SELECT 
                u.user_id,
                u.full_name,
                u.email,
                u.role,
                u.is_manager_approver,
                u.created_at,
                m.full_name as manager_name,
                m.user_id as manager_id,
                c.name as company_name
            FROM Users u
            LEFT JOIN Users m ON u.manager_id = m.user_id
            LEFT JOIN Companies c ON u.company_id = c.company_id
            ORDER BY u.created_at DESC
        """)
        
        users = cursor.fetchall()
        users_list = [dict(user) for user in users]
        
        cursor.close()
        conn.close()
        
        return jsonify(users_list), 200
        
    except Exception as e:
        app.logger.error(f'Failed to fetch users: {e}')
        return jsonify({'message': 'Failed to fetch users'}), 500

@app.route('/api/admin/users', methods=['POST'])
def create_user():
    """Admin creates a new user"""
    try:
        payload = request.get_json() or {}
        full_name = payload.get('full_name')
        email = payload.get('email')
        role = payload.get('role', 'Employee')
        manager_id = payload.get('manager_id')
        
        if not all([full_name, email]):
            return jsonify({'message': 'Full name and email are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT 1 FROM Users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'message': 'Email already exists'}), 400
        
        # Generate temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        password_hash = generate_password_hash(temp_password)
        
        # Set manager approver flag
        is_manager_approver = role.lower() == 'manager'
        
        # Insert user
        cursor.execute("""
            INSERT INTO Users (company_id, full_name, email, password_hash, role, manager_id, is_manager_approver)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """, (1, full_name, email, password_hash, role, manager_id, is_manager_approver))
        
        new_user_id = cursor.fetchone()[0]
        conn.commit();
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'User created successfully',
            'user_id': str(new_user_id),
            'temporary_password': temp_password
        }), 201
        
    except Exception as e:
        app.logger.error(f'Failed to create user: {e}')
        return jsonify({'message': 'Failed to create user'}), 500

@app.route('/api/admin/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Admin updates user role and manager"""
    try:
        payload = request.get_json() or {}
        role = payload.get('role')
        manager_id = payload.get('manager_id')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build update query dynamically
        updates = []
        params = []
        
        if role:
            updates.append("role = %s")
            params.append(role)
            # Update manager approver flag
            updates.append("is_manager_approver = %s")
            params.append(role.lower() == 'manager')
        
        if manager_id is not None:  # Allow setting manager to None
            updates.append("manager_id = %s")
            params.append(manager_id if manager_id else None)
        
        if not updates:
            return jsonify({'message': 'No updates provided'}), 400
        
        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(updates)} WHERE user_id = %s"
        
        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            return jsonify({'message': 'User not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'User updated successfully'}), 200
        
    except Exception as e:
        app.logger.error(f'Failed to update user: {e}')
        return jsonify({'message': 'Failed to update user'}), 500

@app.route('/api/admin/managers', methods=['GET'])
def get_managers():
    """Get all users with manager role for dropdowns"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        cursor.execute("""
            SELECT user_id, full_name, email
            FROM Users 
            WHERE role = 'Manager' OR role = 'Admin'
            ORDER BY full_name
        """)
        
        managers = cursor.fetchall()
        managers_list = [dict(manager) for manager in managers]
        
        cursor.close()
        conn.close()
        
        return jsonify(managers_list), 200
        
    except Exception as e:
        app.logger.error(f'Failed to fetch managers: {e}')
        return jsonify({'message': 'Failed to fetch managers'}), 500

@app.route('/api/admin/send-password/<user_id>', methods=['POST'])
def send_password_reset(user_id):
    """Send password reset to user (simulated for now)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        cursor.execute("SELECT full_name, email FROM Users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Generate new temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        password_hash = generate_password_hash(temp_password)
        
        # Update password
        cursor.execute("UPDATE Users SET password_hash = %s WHERE user_id = %s", (password_hash, user_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # In a real app, you'd send an email here
        app.logger.info(f'Password reset for {user["email"]}: {temp_password}')
        
        return jsonify({
            'message': 'Password reset successfully',
            'temporary_password': temp_password,
            'user_email': user['email']
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to reset password: {e}')
        return jsonify({'message': 'Failed to reset password'}), 500


@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user from the system"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # First, check if user exists and get user details
        cursor.execute("SELECT full_name, email, role FROM Users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Prevent deletion of admin users (safety measure)
        if user['role'] == 'Admin':
            return jsonify({'message': 'Cannot delete admin users for security reasons'}), 403
        
        # Start transaction for safe deletion
        cursor.execute("BEGIN")
        
        try:
            # Check if user has any expenses - prevent deletion if they do
            cursor.execute("SELECT COUNT(*) FROM Expenses WHERE user_id = %s", (user_id,))
            expense_count = cursor.fetchone()[0]
            
            if expense_count > 0:
                cursor.execute("ROLLBACK")
                return jsonify({
                    'message': f'Cannot delete user "{user["full_name"]}" because they have {expense_count} expense(s) in the system. Please transfer or delete their expenses first.'
                }), 400
            
            # Update any approval transactions that reference this user
            cursor.execute("""
                UPDATE ApprovalTransactions 
                SET approver_id = NULL 
                WHERE approver_id = %s
            """, (user_id,))
            
            # Update any users who have this user as manager
            cursor.execute("""
                UPDATE Users 
                SET manager_id = NULL 
                WHERE manager_id = %s
            """, (user_id,))
            
            # Finally, delete the user
            cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
            
            # Check if the deletion was successful
            if cursor.rowcount == 0:
                cursor.execute("ROLLBACK")
                return jsonify({'message': 'User could not be deleted'}), 400
            
            # Commit the transaction
            cursor.execute("COMMIT")
            
            cursor.close()
            conn.close()
            
            app.logger.info(f'User deleted successfully: {user["full_name"]} ({user["email"]})')
            
            return jsonify({
                'message': f'User "{user["full_name"]}" has been successfully deleted',
                'deleted_user': {
                    'user_id': user_id,
                    'full_name': user['full_name'],
                    'email': user['email']
                }
            }), 200
            
        except Exception as e:
            # Rollback on any error during deletion process
            cursor.execute("ROLLBACK")
            raise e
        
    except Exception as e:
        app.logger.error(f'Failed to delete user {user_id}: {e}')
        return jsonify({'message': f'Failed to delete user: {str(e)}'}), 500


@app.route('/api/admin/all-expenses', methods=['GET'])
def get_all_expenses():
    """Get all expenses for admin override capabilities"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Fetch all expenses with user and approver details
        cursor.execute("""
            SELECT 
                e.expense_id,
                e.submitted_amount,
                e.submitted_currency,
                e.converted_amount,
                e.category,
                e.description,
                e.status,
                e.expense_date,
                e.created_at,
                u.full_name as employee_name,
                u.email as employee_email,
                COALESCE(m.full_name, 'No Manager') as current_approver,
                CASE 
                    WHEN e.status = 'Approved' THEN 'Finalized'
                    WHEN e.status = 'Rejected' THEN m.full_name
                    ELSE COALESCE(m.full_name, 'Pending Assignment')
                END as approver_display
            FROM Expenses e
            JOIN Users u ON e.user_id = u.user_id
            LEFT JOIN Users m ON u.manager_id = m.user_id
            ORDER BY e.created_at DESC
        """)
        
        expenses = cursor.fetchall()
        
        # Convert to list of dictionaries for JSON response
        expenses_list = []
        for expense in expenses:
            expenses_list.append({
                'expense_id': expense['expense_id'],
                'employee_name': expense['employee_name'],
                'employee_email': expense['employee_email'],
                'amount': float(expense['submitted_amount']),
                'currency': expense['submitted_currency'],
                'converted_amount': float(expense['converted_amount']),
                'category': expense['category'],
                'description': expense['description'],
                'status': expense['status'],
                'submission_date': expense['expense_date'].strftime('%b %d, %Y') if expense['expense_date'] else '',
                'created_at': expense['created_at'].strftime('%b %d, %Y') if expense['created_at'] else '',
                'current_approver': expense['current_approver'],
                'approver_display': expense['approver_display']
            })
        
        return jsonify(expenses_list), 200
        
    except Exception as e:
        app.logger.error(f'Failed to fetch all expenses: {e}')
        return jsonify({'message': f'Failed to fetch expenses: {str(e)}'}), 500


@app.route('/api/admin/override-expense/<expense_id>', methods=['POST'])
def override_expense(expense_id):
    """Override expense approval/rejection"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'approve' or 'reject'
        
        if action not in ['approve', 'reject']:
            return jsonify({'message': 'Invalid action. Must be approve or reject'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        # Check if expense exists
        cursor.execute("SELECT * FROM Expenses WHERE expense_id = %s", (expense_id,))
        expense = cursor.fetchone()
        
        if not expense:
            return jsonify({'message': 'Expense not found'}), 404
            
        # Update expense status
        new_status = 'Approved' if action == 'approve' else 'Rejected'
        cursor.execute("""
            UPDATE Expenses 
            SET status = %s
            WHERE expense_id = %s
        """, (new_status, expense_id))
        
        conn.commit()
        
        return jsonify({
            'message': f'Expense successfully {action}d via admin override',
            'expense_id': expense_id,
            'new_status': new_status
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to override expense {expense_id}: {e}')
        return jsonify({'message': f'Failed to override expense: {str(e)}'}), 500


# Start the Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)