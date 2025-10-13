#!/usr/bin/env python3
"""
Create a test JWT token for testing KnowledgeTree
"""
import jwt
import os
from datetime import datetime, timedelta

# Path to Core's private key
CORE_DIR = "../hivematrix-core"
PRIVATE_KEY_PATH = os.path.join(CORE_DIR, "keys/jwt_private.pem")

def create_test_token():
    """Create a test user token"""
    if not os.path.exists(PRIVATE_KEY_PATH):
        print(f"❌ Private key not found at {PRIVATE_KEY_PATH}")
        return None

    with open(PRIVATE_KEY_PATH, 'r') as f:
        private_key = f.read()

    # Create a test token similar to what Core would create
    payload = {
        'sub': 'admin',
        'username': 'admin',
        'preferred_username': 'admin',
        'email': 'admin@hivematrix.local',
        'permission_level': 'admin',
        'iss': 'hivematrix-core',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=24),
        'groups': ['admin']
    }

    # Add kid (key ID) to headers to match Core's JWKS
    headers = {
        'kid': 'hivematrix-signing-key-1'
    }

    token = jwt.encode(payload, private_key, algorithm='RS256', headers=headers)
    return token

if __name__ == '__main__':
    token = create_test_token()
    if token:
        print(token)
