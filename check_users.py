#!/usr/bin/env python3
"""
Check what users exist in the database
"""

import psycopg2
from werkzeug.security import check_password_hash
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

def check_users():
    """Check what users exist and verify test credentials"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT full_name, email, role, password_hash FROM Users")
        users = cursor.fetchall()
        
        print("Users in database:")
        print("-" * 50)
        for full_name, email, role, password_hash in users:
            print(f"Name: {full_name}")
            print(f"Email: {email}")
            print(f"Role: {role}")
            
            # Test common passwords
            test_passwords = ['admin123', 'manager123', 'employee123']
            for test_pwd in test_passwords:
                if check_password_hash(password_hash, test_pwd):
                    print(f"Password: {test_pwd} ✓")
                    break
            else:
                print("Password: [Hash doesn't match test passwords]")
            print("-" * 50)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users()
