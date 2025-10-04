#!/usr/bin/env python3
"""
Simple test script to verify the Flask app works correctly
"""

import requests
import json
import sys

BASE_URL = "http://localhost:3000"

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False

def test_registration():
    """Test user registration"""
    test_user = {
        "full_name": "Test User",
        "email": "test@example.com", 
        "password": "test123",
        "role": "employee"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers={"Content-Type": "application/json"},
            data=json.dumps(test_user)
        )
        
        if response.status_code == 201:
            print("✓ Registration test passed")
            return True
        else:
            data = response.json()
            print(f"✗ Registration test failed: {data.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ Registration test error: {e}")
        return False

def test_login():
    """Test user login with test credentials"""
    test_credentials = {
        "email": "mike.employee@flow.com",
        "password": "employee123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(test_credentials)
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Login test passed - Welcome {data['user']['full_name']}")
            return True
        else:
            data = response.json()
            print(f"✗ Login test failed: {data.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ Login test error: {e}")
        return False

def main():
    print("ExpenseFlow API Test Suite")
    print("=" * 30)
    
    tests = [
        ("Health Check", test_health_check),
        ("Registration", test_registration), 
        ("Login", test_login)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        if test_func():
            passed += 1
    
    print(f"\n" + "=" * 30)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
