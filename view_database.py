#!/usr/bin/env python3
"""
View PostgreSQL database details and user data
"""

import psycopg2
from psycopg2 import extras
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ExpenseFlow')
}

def view_database_details():
    """View all database tables and their data"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=extras.DictCursor)
        
        print("📊 ExpenseFlow Database Details")
        print("=" * 50)
        
        # 1. Show all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\n🗂️  Tables in database: {len(tables)}")
        for table in tables:
            print(f"   📋 {table['table_name']}")
        
        # 2. Show all users
        print(f"\n👥 USERS TABLE:")
        print("-" * 30)
        cursor.execute("""
            SELECT user_id, full_name, email, role, 
                   is_manager_approver, created_at,
                   (SELECT full_name FROM Users u2 WHERE u2.user_id = u1.manager_id) as manager_name
            FROM Users u1 
            ORDER BY created_at;
        """)
        users = cursor.fetchall()
        
        for i, user in enumerate(users, 1):
            print(f"{i}. {user['full_name']}")
            print(f"   📧 Email: {user['email']}")
            print(f"   👤 Role: {user['role']}")
            print(f"   🆔 ID: {user['user_id']}")
            print(f"   👨‍💼 Manager: {user['manager_name'] or 'None'}")
            print(f"   📅 Created: {user['created_at']}")
            print()
        
        # 3. Show companies
        print(f"\n🏢 COMPANIES TABLE:")
        print("-" * 30)
        cursor.execute("SELECT * FROM Companies ORDER BY company_id;")
        companies = cursor.fetchall()
        
        for company in companies:
            print(f"Company ID: {company['company_id']}")
            print(f"Name: {company['name']}")
            print(f"Currency: {company['default_currency_code']}")
            print(f"Created: {company['created_at']}")
            print()
        
        # 4. Show expenses if any
        print(f"\n💰 EXPENSES TABLE:")
        print("-" * 30)
        cursor.execute("""
            SELECT e.expense_id, e.description, e.category, e.expense_date,
                   e.submitted_amount, e.submitted_currency, e.status,
                   u.full_name as employee_name
            FROM Expenses e
            JOIN Users u ON e.user_id = u.user_id
            ORDER BY e.expense_date DESC;
        """)
        expenses = cursor.fetchall()
        
        if expenses:
            for expense in expenses:
                print(f"ID: {expense['expense_id']} | {expense['description']}")
                print(f"   Employee: {expense['employee_name']}")
                print(f"   Amount: {expense['submitted_amount']} {expense['submitted_currency']}")
                print(f"   Status: {expense['status']}")
                print(f"   Date: {expense['expense_date']}")
                print()
        else:
            print("No expenses found.")
        
        # 5. Database statistics
        print(f"\n📈 DATABASE STATISTICS:")
        print("-" * 30)
        
        # Count records in each table
        stats = {}
        for table in tables:
            table_name = table['table_name']
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            stats[table_name] = count
            print(f"{table_name}: {count} records")
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ Database connection successful!")
        print(f"📍 Connected to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"🗄️  Database: {DB_CONFIG['database']}")
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print(f"🔧 Check your database connection settings:")
        print(f"   Host: {DB_CONFIG['host']}")
        print(f"   Port: {DB_CONFIG['port']}")
        print(f"   Database: {DB_CONFIG['database']}")
        print(f"   User: {DB_CONFIG['user']}")

if __name__ == "__main__":
    view_database_details()
