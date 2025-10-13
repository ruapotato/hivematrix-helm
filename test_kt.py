#!/usr/bin/env python3
"""
Automated KnowledgeTree testing script
Logs in through Nexus/Keycloak, gets token, tests endpoints, shows logs
"""
import requests
import json
import sys
from urllib.parse import parse_qs, urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NEXUS_URL = "https://localhost:443"
KT_URL = "http://127.0.0.1:5020"

def get_token_from_session():
    """Try to extract token from browser session cookies or provide instructions"""
    print("=" * 60)
    print("  KnowledgeTree Authentication Helper")
    print("=" * 60)
    print()
    print("To get a JWT token for testing:")
    print()
    print("Option 1: From Browser (Recommended)")
    print("-" * 60)
    print("1. Open browser and go to: https://192.168.1.76/")
    print("2. Login with admin/admin")
    print("3. Open Developer Tools (F12) → Network tab")
    print("4. Refresh the page")
    print("5. Click any request to https://192.168.1.76/")
    print("6. Look for 'Authorization' header in Request Headers")
    print("7. Copy the value after 'Bearer '")
    print()
    print("Then run:")
    print("  python test_kt.py set-token '<your-token>'")
    print()
    print("Option 2: Direct Token Test (bypasses auth)")
    print("-" * 60)
    print("Test KnowledgeTree directly without auth:")
    print("  python test_kt.py test-direct")
    print()

def test_direct():
    """Test KnowledgeTree endpoint directly (bypasses Nexus proxy)"""
    print("Testing KnowledgeTree directly at http://127.0.0.1:5020...")
    print()

    # Test health endpoint
    print("1. Testing /health (no auth required)")
    try:
        response = requests.get(f"{KT_URL}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Test browse without auth to see what happens
    print("2. Testing /knowledgetree/browse/ (requires auth)")
    try:
        response = requests.get(f"{KT_URL}/knowledgetree/browse/", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        print()

        if response.status_code == 500:
            print("   ⚠️  Got 500 error! This is the issue.")
            print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

def get_service_token():
    """Get a service-to-service JWT token from Core"""
    print("Getting service token from Core...")
    try:
        import sys
        sys.path.insert(0, '../hivematrix-core')
        from app import app as core_app
        from app.auth import create_service_token

        with core_app.app_context():
            token = create_service_token('helm')
            print(f"✓ Got service token: {token[:50]}...")
            return token
    except Exception as e:
        print(f"✗ Could not get service token: {e}")
        return None

def test_with_token(token):
    """Test KnowledgeTree with a real token"""
    print()
    print("Testing /knowledgetree/browse/ with token...")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f"{KT_URL}/knowledgetree/browse/",
            headers=headers,
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response ({len(response.text)} bytes):")
        print("-" * 60)
        print(response.text[:1000])
        if len(response.text) > 1000:
            print(f"\n... ({len(response.text) - 1000} more bytes)")

        if response.status_code == 500:
            print()
            print("⚠️  Got 500 error! Checking logs...")
            show_logs()

    except Exception as e:
        print(f"Error: {e}")

def test_with_mock_token():
    """Test with a mock token to bypass auth decorator"""
    print("Testing with service authentication...")
    print()

    token = get_service_token()
    if token:
        test_with_token(token)

def show_logs():
    """Show recent logs"""
    import subprocess
    print("=" * 60)
    print("Recent KnowledgeTree Logs")
    print("=" * 60)
    print()
    result = subprocess.run(
        ['python', 'logs_cli.py', 'knowledgetree', '--tail', '30'],
        capture_output=True,
        text=True
    )
    print(result.stdout)

def check_kt_app_logs():
    """Check KnowledgeTree app logs directly"""
    print("=" * 60)
    print("Checking KnowledgeTree App Output")
    print("=" * 60)
    print()

    import subprocess
    result = subprocess.run(
        ['bash', '-c', 'cd ../hivematrix-knowledgetree && tail -30 nohup.out 2>/dev/null || echo "No nohup.out found"'],
        capture_output=True,
        text=True
    )
    print(result.stdout)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test-direct':
            test_direct()
        elif sys.argv[1] == 'test-auth':
            test_with_mock_token()
        elif sys.argv[1] == 'logs':
            show_logs()
        elif sys.argv[1] == 'check':
            test_direct()
            show_logs()
            check_kt_app_logs()
        elif sys.argv[1] == 'full':
            print("=" * 60)
            print("Full KnowledgeTree Test")
            print("=" * 60)
            print()
            test_direct()
            test_with_mock_token()
            show_logs()
        else:
            get_token_from_session()
    else:
        get_token_from_session()
        print()
        print("Quick test without auth:")
        print("-" * 60)
        test_direct()
