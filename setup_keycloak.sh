#!/bin/bash
#
# HiveMatrix Keycloak Setup
# Downloads, installs, and configures Keycloak for HiveMatrix
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Load Keycloak version from config file
source "$SCRIPT_DIR/keycloak_version.conf"

KEYCLOAK_ACTUAL_DIR="$PARENT_DIR/keycloak-${KEYCLOAK_VERSION}"
DOWNLOAD_URL="https://github.com/keycloak/keycloak/releases/download/${KEYCLOAK_VERSION}/keycloak-${KEYCLOAK_VERSION}.zip"

echo ""
echo "================================================================"
echo "  HiveMatrix Keycloak Setup"
echo "================================================================"
echo ""

# Check if Keycloak already exists
if [ -e "$KEYCLOAK_ACTUAL_DIR" ]; then
    echo -e "${YELLOW}Keycloak ${KEYCLOAK_VERSION} already exists at:${NC}"
    echo "  $KEYCLOAK_ACTUAL_DIR"
    echo ""
    read -p "Do you want to delete and reinstall? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "Removing existing Keycloak..."
        rm -rf "$KEYCLOAK_ACTUAL_DIR"
        rm -f "$KEYCLOAK_DIR"  # Remove symlink too
    else
        echo "Using existing Keycloak installation."
        SKIP_DOWNLOAD=true
    fi
fi

# Download Keycloak
if [ "$SKIP_DOWNLOAD" != "true" ]; then
    echo "Downloading Keycloak ${KEYCLOAK_VERSION}..."
    cd "$PARENT_DIR"

    if command -v wget &> /dev/null; then
        wget -q --show-progress "$DOWNLOAD_URL" -O keycloak.zip
    elif command -v curl &> /dev/null; then
        curl -L --progress-bar "$DOWNLOAD_URL" -o keycloak.zip
    else
        echo -e "${RED}Error: Neither wget nor curl is installed${NC}"
        echo "Please install wget or curl and try again"
        exit 1
    fi

    echo ""
    echo "Extracting Keycloak..."
    unzip -q keycloak.zip
    rm keycloak.zip

    echo -e "${GREEN}✓ Keycloak downloaded and extracted${NC}"
fi

# Update Helm's services.json to point to the new Keycloak
echo ""
echo "Updating Helm configuration..."

HELM_SERVICES="$SCRIPT_DIR/services.json"
TEMP_FILE=$(mktemp)

# Read the current services.json and update keycloak path
python3 << EOF
import json

with open('$HELM_SERVICES', 'r') as f:
    services = json.load(f)

# Update or create keycloak entry
if 'keycloak' not in services:
    services['keycloak'] = {
        'url': 'http://localhost:8080',
        'port': 8080,
        'type': 'keycloak',
        'start_command': 'bin/kc.sh start-dev'
    }

services['keycloak']['path'] = '../keycloak-${KEYCLOAK_VERSION}'

with open('$TEMP_FILE', 'w') as f:
    json.dump(services, f, indent=2)
EOF

mv "$TEMP_FILE" "$HELM_SERVICES"

echo -e "${GREEN}✓ Helm configuration updated${NC}"

# Setup Helm Python environment if needed
echo ""
echo "Checking Helm environment..."

cd "$SCRIPT_DIR"

if [ ! -d "pyenv" ]; then
    echo -e "${YELLOW}Setting up Helm Python environment...${NC}"

    # Detect OS for package installation
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        OS="unknown"
    fi

    # Install Python venv package if needed
    if ! python3 -m venv --help &> /dev/null; then
        echo "Installing Python venv package..."
        if [[ "$OS" == "fedora" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "centos" ]]; then
            sudo dnf install -y python3-virtualenv
        elif [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
            sudo apt update
            sudo apt install -y python3-venv
        else
            echo -e "${RED}Unable to install python3-venv automatically${NC}"
            echo "Please install it manually and re-run this script"
            exit 1
        fi
    fi

    # Create virtual environment
    python3 -m venv pyenv
    source pyenv/bin/activate

    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    echo -e "${GREEN}✓ Helm environment ready${NC}"
else
    echo -e "${GREEN}✓ Helm environment exists${NC}"
    source pyenv/bin/activate
fi

# Start Keycloak
echo ""
echo "================================================================"
echo "  Starting Keycloak"
echo "================================================================"
echo ""

# Stop any running Keycloak instances
echo "Stopping any existing Keycloak instances..."
pkill -f "keycloak.*start-dev" 2>/dev/null || true
sleep 2

# Start Keycloak directly (not via Helm CLI)
echo "Starting Keycloak (this takes ~20 seconds)..."
cd "$KEYCLOAK_ACTUAL_DIR"

export KEYCLOAK_ADMIN=admin
export KEYCLOAK_ADMIN_PASSWORD=admin

# Start in background
nohup bin/kc.sh start-dev > /tmp/keycloak-setup.log 2>&1 &
KEYCLOAK_PID=$!

echo ""
echo "Waiting for Keycloak to initialize..."
for i in {1..40}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Keycloak is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

cd "$SCRIPT_DIR"

echo ""
echo ""
echo "================================================================"
echo -e "${GREEN}  Keycloak Setup Complete!${NC}"
echo "================================================================"
echo ""
echo "Keycloak Admin Console: http://localhost:8080"
echo "Admin credentials:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "Next steps:"
echo "  1. Run: ./configure_keycloak.sh"
echo "     This will automatically:"
echo "     - Create the hivematrix realm"
echo "     - Create core-client and retrieve the secret"
echo "     - Create the admin user (admin/admin)"
echo "     - Configure group mappings"
echo ""
echo "  2. Then you can start the full system with: ./start.sh"
echo ""
echo "================================================================"
echo ""
