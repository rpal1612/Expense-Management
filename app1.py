from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import re
from datetime import datetime
import traceback
import psycopg2
from psycopg2.extras import RealDictCursor, extras
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import json
from pathlib import Path
from dotenv import load_dotenv

app = Flask(_name_)
CORS(app)
app.secret_key = 'your-secret-key-here-change-in-production'

# --- CONFIGURATION ---
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Database Configuration
DATABASE_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'root',
    'port': 5433
}

# Tesseract Configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Base directory for serving static files
BASE_DIR = os.path.dirname(os.path.abspath(_file_))

# Load environment variables
env_path = Path(BASE_DIR) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# --- DATABASE FUNCTIONS ---

def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        print("✅ Database connection successful")
        return conn
    except psycopg2.Error as e:
        print(f"❌ Database connection error: {e}")
        return None

def init_database():
    """Initialize the database and create necessary tables."""
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to database!")
        return False

    try:
        cursor = conn.cursor()
        
        # Create expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                amount DECIMAL(10, 2) NOT NULL,
                currency VARCHAR(10) NOT NULL,
                category VARCHAR(100) NOT NULL,
                date DATE NOT NULL,
                description TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                employee_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create users table for authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                company_id INTEGER DEFAULT 1,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'Employee',
                is_manager_approver BOOLEAN DEFAULT FALSE,
                manager_id INTEGER REFERENCES users(user_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create approval transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_transactions (
                transaction_id SERIAL PRIMARY KEY,
                expense_id INTEGER REFERENCES expenses(id),
                approver_id INTEGER REFERENCES users(user_id),
                step_sequence INTEGER,
                status VARCHAR(20),
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        
        conn.commit()
        print("✅ Database initialized successfully!")
        
        # Create test users
        create_test_users(cursor, conn)
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database initialization error: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            cursor.close()
            conn.close()

def create_test_users(cursor, conn):
    """Create test users if they don't exist."""
    try:
        # Check if test users already exist
        cursor.execute("SELECT COUNT(*) FROM users WHERE email LIKE '%@flow.com'")
        existing_users = cursor.fetchone()[0]
        
        if existing_users == 0:
            print('Creating test users...')
            
            # Test users with hashed passwords
            test_users = [
                ('John Doe', 'john.admin@flow.com', 'admin123', 'Admin', True, None),
                ('Sarah Johnson', 'sarah.manager@flow.com', 'manager123', 'Manager', True, None),
                ('Mike Chen', 'mike.employee@flow.com', 'employee123', 'Employee', False, 2),
                ('Emily Davis', 'emily.employee@flow.com', 'employee123', 'Employee', False, 2),
                ('David Wilson', 'david.employee@flow.com', 'employee123', 'Employee', False, 2)
            ]
            
            user_ids = {}
            
            for full_name, email, password, role, is_manager_approver, manager_id in test_users:
                password_hash = generate_password_hash(password)
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role, is_manager_approver, manager_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING user_id;
                """, (full_name, email, password_hash, role, is_manager_approver, manager_id))
                
                user_id = cursor.fetchone()[0]
                user_ids[email] = user_id
            
            # Update manager relationships
            cursor.execute("""
                UPDATE users 
                SET manager_id = %s
                WHERE email = 'sarah.manager@flow.com'
            """, (user_ids['john.admin@flow.com'],))
            
            conn.commit()
            print('✅ Test users created successfully.')
            print('Test credentials:')
            print('  Admin: john.admin@flow.com / admin123')
            print('  Manager: sarah.manager@flow.com / manager123')
            print('  Employee: mike.employee@flow.com / employee123')
            print('  Employee: emily.employee@flow.com / employee123')
        else:
            print('✅ Test users already exist.')
            
    except Exception as e:
        print(f'❌ Failed to create test users: {e}')
        conn.rollback()

# --- EXPENSE MANAGEMENT FUNCTIONS ---

def save_expense_to_db(expense_data):
    """Save expense data to PostgreSQL database."""
    print(f"🔍 Attempting to save expense: {expense_data}")
    
    conn = get_db_connection()
    if conn is None:
        return False, "Database connection failed"
    
    try:
        cursor = conn.cursor()
        
        # Validate and convert date
        try:
            date_obj = datetime.strptime(expense_data['date'], '%Y-%m-%d').date()
        except ValueError as e:
            return False, f"Invalid date format: {e}"
        
        # Validate and convert amount
        try:
            amount = float(expense_data['amount'])
        except (ValueError, TypeError) as e:
            return False, f"Invalid amount: {e}"
        
        print(f"💾 Inserting into DB:")
        print(f"   Amount: {amount}")
        print(f"   Currency: {expense_data['currency']}")
        print(f"   Category: {expense_data['category']}")
        print(f"   Date: {date_obj}")
        print(f"   Description: {expense_data['description']}")
        
        cursor.execute("""
            INSERT INTO expenses (amount, currency, category, date, description, employee_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            RETURNING id;
        """, (
            amount,
            expense_data['currency'],
            expense_data['category'],
            date_obj,
            expense_data['description'],
            expense_data.get('employee_name', 'Unknown Employee')
        ))
        
        expense_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Expense saved successfully with ID: {expense_id}")
        return True, expense_id
        
    except psycopg2.Error as e:
        error_msg = f"Database error: {e}"
        print(f"❌ {error_msg}")
        print(f"🔍 Full error details: {traceback.format_exc()}")
        conn.rollback()
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"❌ {error_msg}")
        print(f"🔍 Full error details: {traceback.format_exc()}")
        conn.rollback()
        return False, error_msg
    finally:
        if conn:
            cursor.close()
            conn.close()

def get_all_expenses():
    """Retrieve all expenses from the database."""
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM expenses ORDER BY date DESC, created_at DESC;")
        expenses = cursor.fetchall()
        print(f"📊 Retrieved {len(expenses)} expenses from database")
        return expenses
    except psycopg2.Error as e:
        print(f"❌ Error fetching expenses: {e}")
        return []
    finally:
        if conn:
            cursor.close()
            conn.close()

def get_pending_expenses():
    """Retrieve pending expenses for approval."""
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM expenses WHERE status = 'pending' ORDER BY date DESC, created_at DESC;")
        expenses = cursor.fetchall()
        return expenses
    except psycopg2.Error as e:
        print(f"❌ Error fetching pending expenses: {e}")
        return []
    finally:
        if conn:
            cursor.close()
            conn.close()

def update_expense_status(expense_id, status, comments="", approver_id=None):
    """Update expense status and log approval transaction."""
    conn = get_db_connection()
    if conn is None:
        return False, "Database connection failed"
    
    try:
        cursor = conn.cursor()
        
        # Update expense status
        cursor.execute("""
            UPDATE expenses 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, expense_id))
        
        # Log approval transaction if approver provided
        if approver_id:
            cursor.execute("""
                INSERT INTO approval_transactions (expense_id, approver_id, status, comments)
                VALUES (%s, %s, %s, %s)
            """, (expense_id, approver_id, status, comments))
        
        conn.commit()
        return True, "Expense status updated successfully"
        
    except psycopg2.Error as e:
        error_msg = f"Database error: {e}"
        print(f"❌ {error_msg}")
        conn.rollback()
        return False, error_msg
    finally:
        if conn:
            cursor.close()
            conn.close()

# --- RECEIPT PROCESSING FUNCTIONS ---

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_amount(text):
    text = text.replace(',', '').replace('  ', ' ')
    patterns = [
        r'total\s*[:\s]\s*(?:rs\.?|₹)?\s*(\d+(?:\.\d{1,2})?)',
        r'amount\s*[:\s]\s*(\d+(?:\.\d{1,2})?)',
        r'(?:rs\.?|₹)\s*(\d+(?:\.\d{1,2})?)',
        r'\$\s*(\d+(?:\.\d{1,2})?)',
        r'(?:^|\s)(\d{3,}(?:\.\d{1,2})?)(?:\s|$)',
    ]
    amounts = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                amount = float(match.group(1))
                if 10 < amount < 10000000:
                    amounts.append(amount)
            except (ValueError, IndexError):
                continue
    if amounts:
        return str(int(max(amounts)))
    return ''

def extract_currency(text):
    text_upper = text.upper()
    if '₹' in text or 'INR' in text_upper or 'RS' in text_upper or 'RUPEE' in text_upper:
        return 'INR'
    elif '€' in text or 'EUR' in text_upper or 'EURO' in text_upper:
        return 'EUR'
    elif '£' in text or 'GBP' in text_upper or 'POUND' in text_upper:
        return 'GBP'
    elif '$' in text or 'USD' in text_upper or 'DOLLAR' in text_upper:
        return 'USD'
    else:
        return 'INR'

def extract_date(text):
    patterns = [
        r'date\s*[:\s]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2})',
        r'(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',
        r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
    ]
    date_formats_to_try = [
        '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
        '%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d',
        '%d %B %Y', '%d %b %Y', '%d %B %y', '%d %b %y'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            for fmt in date_formats_to_try:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
    return ''

def extract_category(text):
    text_lower = text.lower()
    categories = {
        'Food & Dining': ['restaurant', 'cafe', 'food', 'diner', 'pizza', 'kitchen', 'eatery'],
        'Transportation': ['fuel', 'gas', 'petrol', 'taxi', 'uber', 'ola', 'transport', 'parking'],
        'Groceries': ['grocery', 'supermarket', 'market', 'mart', 'kirana'],
        'Office Supplies': ['office', 'stationery', 'printing', 'paper', 'xerox', 'supplies'],
        'Lodging': ['hotel', 'motel', 'resort', 'accommodation', 'lodge', 'stay'],
        'Entertainment': ['cinema', 'movie', 'theatre', 'theater', 'game'],
    }
    for category, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            return category
    return 'Miscellaneous'

def extract_description(text, lines):
    desc_match = re.search(r'description\s*[:\s]\s*(.+?)(?:\n|$)', text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        desc_text = desc_match.group(1).strip()
        return re.sub(r'\s+', ' ', desc_text)[:250]
    description_parts = []
    skip_words = ['receipt', 'invoice', 'bill', 'tax', 'total', 'amount', 'date', 'cash', 'change', 'gst']
    for line in lines:
        line = line.strip()
        if len(line) < 4 or re.match(r'^[\d\s\-/.,:₹$]+$', line):
            continue
        if any(word in line.lower() for word in skip_words):
            continue
        description_parts.append(line)
        if len(description_parts) >= 2:
            break
    if description_parts:
        return ' - '.join(description_parts)[:250]
    return ''

def extract_receipt_data(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        data = {
            'amount': extract_amount(text),
            'currency': extract_currency(text),
            'date': extract_date(text),
            'category': extract_category(text),
            'description': extract_description(text, lines)
        }
        print(f"📄 Extracted receipt data: {data}")
        return data
    except Exception as e:
        print(f"ERROR extracting data: {e}")
        return {}

# --- ROUTES ---

# Main pages
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manager')
def manager_dashboard():
    return render_template('manager_dashboard.html')

# Receipt processing routes
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'receipt' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    file = request.files['receipt']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        receipt_data = extract_receipt_data(filepath)
        session['receipt_data'] = receipt_data
        os.remove(filepath)
        return redirect(url_for('result'))
    flash('Invalid file type.', 'error')
    return redirect(url_for('index'))

@app.route('/result')
def result():
    receipt_data = session.get('receipt_data', {})
    print(f"📋 Displaying result data: {receipt_data}")
    return render_template('result.html', data=receipt_data)

@app.route('/submit', methods=['POST'])
def submit():
    """Handles the final submission of the confirmed expense data."""
    print("🔄 SUBMIT ROUTE CALLED")
    print(f"📥 Form data received: {dict(request.form)}")
    
    expense_data = {
        'amount': request.form.get('amount', '').strip(),
        'currency': request.form.get('currency', '').strip(),
        'category': request.form.get('category', '').strip(),
        'date': request.form.get('date', '').strip(),
        'description': request.form.get('description', '').strip(),
        'employee_name': request.form.get('employee_name', 'Unknown Employee')
    }

    print(f"🔍 Processed expense data: {expense_data}")

    # Server-side validation
    validation_errors = []
    if not expense_data['amount']:
        validation_errors.append('Amount is required.')
    
    if not expense_data['date']:
        validation_errors.append('Date is required.')
    
    if validation_errors:
        for error in validation_errors:
            flash(error, 'error')
        session['receipt_data'] = expense_data
        return redirect(url_for('result'))
    
    # Set defaults if empty
    if not expense_data['currency']:
        expense_data['currency'] = 'INR'
    
    if not expense_data['category']:
        expense_data['category'] = 'Miscellaneous'

    if not expense_data['description']:
        expense_data['description'] = 'No description'

    print(f"💾 Final expense data to save: {expense_data}")
    
    success, result = save_expense_to_db(expense_data)
    
    if success:
        flash(f'Expense saved successfully! (ID: {result})', 'success')
        session.pop('receipt_data', None)
    else:
        flash(f'Error saving expense: {result}', 'error')
        # Keep the data in session for correction
        session['receipt_data'] = expense_data
    
    return redirect(url_for('index'))

@app.route('/expenses')
def view_expenses():
    expenses = get_all_expenses()
    print(f"📋 Displaying {len(expenses)} expenses")
    return render_template('expenses.html', expenses=expenses)

# API Routes for Manager Dashboard
@app.route('/api/manager/dashboard')
def manager_dashboard_data():
    """API endpoint for manager dashboard data"""
    try:
        all_expenses = get_all_expenses()
        pending_expenses = get_pending_expenses()
        
        # Calculate total spent (only approved expenses)
        total_spent = sum(float(expense['amount']) for expense in all_expenses if expense['status'] == 'approved')
        
        response_data = {
            "totalSpentYTD": total_spent,
            "pendingApprovals": pending_expenses,
            "allTeamExpenses": all_expenses
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error fetching dashboard data: {e}")
        return jsonify({"error": "Failed to fetch dashboard data"}), 500

@app.route('/api/expenses/process', methods=['POST'])
def process_approval():
    """API endpoint to process expense approvals/rejections"""
    try:
        data = request.get_json()
        expense_id = data.get('expenseId')
        action = data.get('action')  # 'approve' or 'reject'
        comments = data.get('comments', '')
        
        if not expense_id or not action:
            return jsonify({"error": "Missing required fields"}), 400
        
        # Map action to status
        status = 'approved' if action.lower() == 'approve' else 'rejected'
        
        success, message = update_expense_status(expense_id, status, comments)
        
        if success:
            return jsonify({
                "message": f"Expense {action}ed successfully",
                "newStatus": status
            })
        else:
            return jsonify({"error": message}), 500
            
    except Exception as e:
        print(f"❌ Error processing approval: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Authentication routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Handle user login"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'message': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            user_data = {
                'user_id': user['user_id'],
                'full_name': user['full_name'],
                'email': user['email'],
                'role': user['role']
            }
            
            # Determine redirect based on role
            if user['role'].lower() == 'admin':
                redirect_path = '/admin/dashboard'
            elif user['role'].lower() == 'manager':
                redirect_path = '/manager'
            else:
                redirect_path = '/employee/dashboard'
                
            return jsonify({
                'message': 'Login successful',
                'user': user_data,
                'redirect': redirect_path
            })
        else:
            return jsonify({'message': 'Invalid credentials'}), 401
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'message': 'Internal server error'}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Handle user registration"""
    data = request.get_json()
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Employee')
    
    if not all([full_name, email, password]):
        return jsonify({'message': 'All fields are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'message': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Check if email exists
        cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'message': 'Email already registered'}), 400
        
        # Hash password and create user
        password_hash = generate_password_hash(password)
        is_manager_approver = (role.lower() == 'manager')
        
        cursor.execute("""
            INSERT INTO users (full_name, email, password_hash, role, is_manager_approver)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
        """, (full_name, email, password_hash, role, is_manager_approver))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user_id
        }), 201
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        conn.rollback()
        return jsonify({'message': 'Internal server error'}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()

# Debug routes
@app.route('/debug-db')
def debug_db():
    """Debug endpoint to check database status"""
    conn = get_db_connection()
    if conn is None:
        return "❌ Database connection failed"
    
    try:
        cursor = conn.cursor()
        
        # Check table existence
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'expenses'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM expenses;")
        count = cursor.fetchone()[0]
        
        # Get recent expenses
        cursor.execute("SELECT id, amount, category, date, status FROM expenses ORDER BY id DESC LIMIT 5;")
        recent_expenses = cursor.fetchall()
        
        result = f"""
        <h2>Database Debug Info</h2>
        <p>✅ Database connected</p>
        <p>Table exists: {table_exists}</p>
        <p>Total expenses: {count}</p>
        <h3>Recent Expenses (last 5):</h3>
        <ul>
        """
        
        for expense in recent_expenses:
            result += f"<li>ID: {expense[0]}, Amount: {expense[1]}, Category: {expense[2]}, Date: {expense[3]}, Status: {expense[4]}</li>"
        
        result += "</ul>"
        return result
        
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        if conn:
            cursor.close()
            conn.close()

@app.route('/test-add-expense')
def test_add_expense():
    """Test route to manually add an expense"""
    test_data = {
        'amount': '100.50',
        'currency': 'INR',
        'category': 'Food & Dining',
        'date': '2024-01-15',
        'description': 'Test expense from debug route',
        'employee_name': 'Test User'
    }
    
    success, result = save_expense_to_db(test_data)
    
    if success:
        return f"✅ Test expense added successfully! ID: {result}"
    else:
        return f"❌ Failed to add test expense: {result}"

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({'status': 'healthy', 'database': 'connected'})
        else:
            return jsonify({'status': 'degraded', 'database': 'disconnected'}), 503
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# --- INITIALIZATION ---
if _name_ == '_main_':
    print("🚀 Initializing ExpenseFlow Application...")
    print("📊 Initializing database...")
    init_database()
    print("🌐 Starting Flask server...")
    app.run(debug=True, port=5000)
