#!/bin/bash
#
# HiveMatrix App Installer Template
# This script should be customized for each app
#

set -e  # Exit on error

APP_NAME="__APP_NAME__"  # Replace with actual app name (e.g., "core", "codex")
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=========================================="
echo "  Installing $APP_NAME"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check Python version
echo -e "${YELLOW}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Found Python $PYTHON_VERSION${NC}"
echo ""

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ -d "pyenv" ]; then
    echo "  Virtual environment already exists"
else
    python3 -m venv pyenv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Activate virtual environment
source pyenv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"
echo ""

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""
fi

# Create instance directory if needed
if [ ! -d "instance" ]; then
    echo -e "${YELLOW}Creating instance directory...${NC}"
    mkdir -p instance
    echo -e "${GREEN}✓ Instance directory created${NC}"
    echo ""
fi

# App-specific setup
echo -e "${YELLOW}Running app-specific setup...${NC}"

# __CUSTOM_SETUP_START__
# Add custom setup commands here for each app
# Examples:
#   - Database initialization
#   - Configuration file creation
#   - Additional dependencies

# For Core: Setup Keycloak client
# For Codex: Setup PostgreSQL database
# For Ledger: Setup PostgreSQL database
# For KnowledgeTree: Setup Neo4j database

# __CUSTOM_SETUP_END__

echo -e "${GREEN}✓ App-specific setup complete${NC}"
echo ""

echo "=========================================="
echo -e "${GREEN}  $APP_NAME installed successfully!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Configure the app in instance/ directory"
echo "  2. Start the app with: ./start.sh"
echo ""
