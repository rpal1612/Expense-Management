#!/usr/bin/env python3
"""
Test both signup and login functionality
"""

import requests
import json

BASE_URL = "http://localhost:3000"

def test_signup_and_login():
    """Test signup with new user and then login"""
    
    # Test 1: Sign up a new user
    print("🔥 Testing Signup...")
    new_user = {
        "full_name": "Jane Smith",
        "email": "jane.smith@test.com",
        "password": "test123456",
        "role": "employee"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(new_user)
    )
    
    if response.status_code == 201:
        print("✅ Signup successful!")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Signup failed: {response.json()}")
        return False
    
    # Test 2: Login with the new user
    print("\n🔑 Testing Login with new user...")
    login_data = {
        "email": "jane.smith@test.com",
        "password": "test123456"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(login_data)
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful with new user!")
        print(f"   User: {data['user']['full_name']} ({data['user']['role']})")
        print(f"   Redirect: {data['redirect']}")
    else:
        print(f"❌ Login failed: {response.json()}")
        return False
    
    # Test 3: Login with existing test user
    print("\n🧪 Testing Login with existing test user...")
    test_login = {
        "email": "mike.employee@flow.com",
        "password": "employee123"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_login)
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful with test user!")
        print(f"   User: {data['user']['full_name']} ({data['user']['role']})")
        print(f"   Redirect: {data['redirect']}")
    else:
        print(f"❌ Login failed: {response.json()}")
        return False
    
    return True

if __name__ == "__main__":
    print("ExpenseFlow Signup & Login Test")
    print("=" * 35)
    
    if test_signup_and_login():
        print("\n🎉 All tests passed! Both signup and login are working perfectly!")
    else:
        print("\n❌ Some tests failed!")
