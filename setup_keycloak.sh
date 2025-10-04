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

KEYCLOAK_VERSION="26.0.5"
KEYCLOAK_DIR="/home/david/work/keycloak-${KEYCLOAK_VERSION}"
DOWNLOAD_URL="https://github.com/keycloak/keycloak/releases/download/${KEYCLOAK_VERSION}/keycloak-${KEYCLOAK_VERSION}.zip"

echo ""
echo "================================================================"
echo "  HiveMatrix Keycloak Setup"
echo "================================================================"
echo ""

# Check if Keycloak already exists
if [ -d "$KEYCLOAK_DIR" ]; then
    echo -e "${YELLOW}Keycloak ${KEYCLOAK_VERSION} already exists at:${NC}"
    echo "  $KEYCLOAK_DIR"
    echo ""
    read -p "Do you want to delete and reinstall? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "Removing existing Keycloak..."
        rm -rf "$KEYCLOAK_DIR"
    else
        echo "Using existing Keycloak installation."
        SKIP_DOWNLOAD=true
    fi
fi

# Download Keycloak
if [ "$SKIP_DOWNLOAD" != "true" ]; then
    echo "Downloading Keycloak ${KEYCLOAK_VERSION}..."
    cd /home/david/work

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

HELM_SERVICES="/home/david/work/hivematrix-helm/services.json"
TEMP_FILE=$(mktemp)

# Read the current services.json and update keycloak path
python3 << EOF
import json

with open('$HELM_SERVICES', 'r') as f:
    services = json.load(f)

# Update keycloak path
if 'keycloak' in services:
    services['keycloak']['path'] = '../keycloak-${KEYCLOAK_VERSION}'

with open('$TEMP_FILE', 'w') as f:
    json.dump(services, f, indent=2)
EOF

mv "$TEMP_FILE" "$HELM_SERVICES"

echo -e "${GREEN}✓ Helm configuration updated${NC}"

# Start Keycloak
echo ""
echo "================================================================"
echo "  Starting Keycloak"
echo "================================================================"
echo ""

cd /home/david/work/hivematrix-helm
source pyenv/bin/activate

# Stop any running Keycloak
python cli.py stop keycloak 2>/dev/null || true
sleep 2

# Start Keycloak
echo "Starting Keycloak (this takes ~20 seconds)..."
python cli.py start keycloak

echo ""
echo "Waiting for Keycloak to initialize..."
for i in {1..30}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Keycloak is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

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
echo "  1. Login to Keycloak admin console"
echo "  2. Run: ./configure_keycloak.sh"
echo "     This will automatically create the hivematrix realm,"
echo "     core-client, and test user"
echo ""
echo "================================================================"
echo ""
