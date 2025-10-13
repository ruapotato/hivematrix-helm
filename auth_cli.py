#!/usr/bin/env python3
"""
Quick CLI tool to login and get JWT token for testing
Usage: python auth_cli.py [username] [password]
       python auth_cli.py test <url>  # Test URL with stored token
"""
import sys
import os
import requests
from pathlib import Path

TOKEN_FILE = Path.home() / '.hivematrix_token'

def login(username='admin', password='admin'):
    """Login and get JWT token"""
    # Try to login through Nexus (Keycloak)
    print(f"🔐 Logging in as {username}...")

    # For now, since Keycloak auth is complex, let's create a simpler direct token getter
    # This would need to be updated with actual Keycloak OIDC flow

    print("⚠️  Keycloak OAuth flow requires browser interaction")
    print("For now, please provide a token manually or use browser dev tools")
    print("\nTo get a token:")
    print("1. Open https://localhost:443/ in browser")
    print("2. Login with admin/admin")
    print("3. Open Developer Tools (F12) → Application → Cookies")
    print("4. Find 'access_token' or 'session' cookie")
    print("5. Run: python auth_cli.py set-token '<your-token>'")

def set_token(token):
    """Manually set token"""
    TOKEN_FILE.write_text(token)
    print(f"✓ Token saved to {TOKEN_FILE}")

def get_token():
    """Get stored token"""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None

def test_endpoint(url):
    """Test URL with stored token"""
    token = get_token()
    if not token:
        print("❌ No token found. Run login first.")
        return

    print(f"🧪 Testing: {url}")
    print(f"Token: {token[:20]}...")

    try:
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {token}'},
            verify=False  # For local HTTPS
        )
        print(f"\nStatus: {response.status_code}")
        print(f"Response ({len(response.text)} bytes):")
        print("-" * 60)
        print(response.text[:1000])
        if len(response.text) > 1000:
            print(f"\n... ({len(response.text) - 1000} more bytes)")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='HiveMatrix Auth CLI')
    parser.add_argument('action', nargs='?', default='login',
                        help='Action: login, set-token, test')
    parser.add_argument('args', nargs='*', help='Arguments for action')

    args = parser.parse_args()

    if args.action == 'login':
        username = args.args[0] if args.args else 'admin'
        password = args.args[1] if len(args.args) > 1 else 'admin'
        login(username, password)
    elif args.action == 'set-token':
        if not args.args:
            print("❌ Token required")
            sys.exit(1)
        set_token(args.args[0])
    elif args.action == 'test':
        if not args.args:
            print("❌ URL required")
            sys.exit(1)
        test_endpoint(args.args[0])
    else:
        print(f"❌ Unknown action: {args.action}")
