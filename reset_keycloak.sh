#!/bin/bash
#
# Reset Keycloak - Clears all data and allows fresh admin setup
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "================================================================"
echo "  Keycloak Reset Tool"
echo "================================================================"
echo ""
echo -e "${YELLOW}WARNING: This will delete ALL Keycloak data!${NC}"
echo ""
echo "This includes:"
echo "  - All realms (including hivematrix if it exists)"
echo "  - All users"
echo "  - All clients"
echo "  - All configurations"
echo ""
echo "After reset, you'll need to reconfigure Keycloak from scratch."
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo "Stopping Keycloak..."

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
source pyenv/bin/activate 2>/dev/null || true

# Stop Keycloak
python cli.py stop keycloak 2>/dev/null || echo "  (Keycloak may not be running)"

echo ""
echo "Deleting Keycloak data directory..."

# Delete the data directory
KEYCLOAK_DATA="/home/david/work/keycloak-26.3.5/data"
if [ -d "$KEYCLOAK_DATA" ]; then
    rm -rf "$KEYCLOAK_DATA"
    echo -e "${GREEN}✓ Data directory deleted${NC}"
else
    echo "  Data directory not found (already clean)"
fi

echo ""
echo "Starting Keycloak with new admin credentials..."
echo ""

# Start Keycloak with admin credentials
cd /home/david/work/keycloak-26.3.5

export KEYCLOAK_ADMIN=admin
export KEYCLOAK_ADMIN_PASSWORD=admin

echo "Starting Keycloak in the background..."
nohup bin/kc.sh start-dev > /tmp/keycloak-startup.log 2>&1 &
KEYCLOAK_PID=$!

echo "Waiting for Keycloak to initialize (this takes ~20 seconds)..."
echo "You can watch the progress in another terminal with:"
echo "  tail -f /tmp/keycloak-startup.log"
echo ""

# Wait for Keycloak to be ready
for i in {1..40}; do
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
echo -e "${GREEN}  Keycloak Reset Complete!${NC}"
echo "================================================================"
echo ""
echo "Admin credentials:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "Next steps:"
echo ""
echo "1. Visit Keycloak Admin Console:"
echo "   http://localhost:8080"
echo ""
echo "2. Follow the setup instructions:"
echo "   ./check_keycloak_setup.sh"
echo ""
echo "================================================================"
echo ""
