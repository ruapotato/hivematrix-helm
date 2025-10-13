#!/bin/bash
# Generate a service token from Core for testing
cd ../hivematrix-core
source pyenv/bin/activate

# Load environment before importing app
python3 << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv('.flaskenv')

from app import app
from app.auth import create_service_token

with app.app_context():
    token = create_service_token('helm')
    print(token)
EOF
