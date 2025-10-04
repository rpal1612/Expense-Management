#!/usr/bin/env python3
"""
Database Setup Script for ExpenseFlow
This script sets up the PostgreSQL database with proper password hashes.
"""

import psycopg2
from werkzeug.security import generate_password_hash
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

def update_user_passwords():
    """Update user passwords with proper hashes"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Test users with default passwords
        test_users = [
            ('john.admin@flow.com', 'admin123', 'Admin'),
            ('sarah.manager@flow.com', 'manager123', 'Manager'),
            ('mike.employee@flow.com', 'employee123', 'Employee'),
            ('emily.employee@flow.com', 'employee123', 'Employee')
        ]
        
        for email, password, role in test_users:
            password_hash = generate_password_hash(password)
            cursor.execute(
                "UPDATE Users SET password_hash = %s WHERE email = %s",
                (password_hash, email)
            )
            print(f"Updated password for {email} ({role})")
        
        conn.commit()
        print("All passwords updated successfully!")
        
    except Exception as e:
        print(f"Error updating passwords: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def test_database_connection():
    """Test database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"Connected to PostgreSQL: {version[0]}")
        
        # Check if ExpenseFlow database exists and has tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables in database")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

if __name__ == "__main__":
    print("ExpenseFlow Database Setup")
    print("=" * 30)
    
    if test_database_connection():
        print("\n✓ Database connection successful")
        print("Updating user passwords...")
        update_user_passwords()
        print("\n✓ Setup completed!")
        print("\nTest Credentials:")
        print("Admin: john.admin@flow.com / admin123")
        print("Manager: sarah.manager@flow.com / manager123") 
        print("Employee: mike.employee@flow.com / employee123")
        print("Employee: emily.employee@flow.com / employee123")
    else:
        print("\n✗ Database connection failed")
        print("Please ensure PostgreSQL is running and database 'ExpenseFlow' exists")
