#!/usr/bin/env python3
"""
Update user passwords with proper hashes
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

def update_passwords():
    """Update user passwords with proper hashes"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # User credentials to update
        users_to_update = [
            ('john.admin@flow.com', 'admin123'),
            ('sarah.manager@flow.com', 'manager123'),
            ('mike.employee@flow.com', 'employee123'),
            ('emily.employee@flow.com', 'employee123')
        ]
        
        for email, password in users_to_update:
            password_hash = generate_password_hash(password)
            cursor.execute(
                "UPDATE Users SET password_hash = %s WHERE email = %s",
                (password_hash, email)
            )
            print(f"✓ Updated password for {email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 All passwords updated successfully!")
        print("\nTest credentials:")
        print("  Admin: john.admin@flow.com / admin123")
        print("  Manager: sarah.manager@flow.com / manager123")
        print("  Employee: mike.employee@flow.com / employee123")
        print("  Employee: emily.employee@flow.com / employee123")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_passwords()
