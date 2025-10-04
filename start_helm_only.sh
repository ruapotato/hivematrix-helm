#!/bin/bash
# HiveMatrix Helm - Development Startup Script

set -e  # Exit on error

echo "🚀 Starting HiveMatrix Helm..."
echo

# Check if virtual environment exists
if [ ! -d "pyenv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv pyenv"
    echo "Then: source pyenv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if database is initialized
if [ ! -f "instance/helm.conf" ]; then
    echo "❌ Database not initialized!"
    echo "Please run: python init_db.py"
    exit 1
fi

# Check if database connection is configured in the config file
if ! grep -q "connection_string" instance/helm.conf; then
    echo "❌ Database not configured in instance/helm.conf"
    echo "Please run: python init_db.py"
    exit 1
fi

# Activate virtual environment
echo "✓ Activating virtual environment..."
source pyenv/bin/activate

# Check if Core is running
echo "✓ Checking Core service..."
CORE_URL=$(grep CORE_SERVICE_URL .flaskenv | cut -d"'" -f2)
if ! curl -s "${CORE_URL}/health" > /dev/null 2>&1; then
    echo "⚠️  Warning: Core service not responding at ${CORE_URL}"
    echo "   Helm will work but authentication may fail"
    echo
fi

# Start Helm
echo "✓ Starting Helm on port 5004..."
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Helm Dashboard: http://localhost:5004"
echo "  Health Check:   http://localhost:5004/health"
echo "  API Docs:       See README.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

python run.py
