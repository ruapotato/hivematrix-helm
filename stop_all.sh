#!/bin/bash
#
# HiveMatrix Helm - Stop All Services Script
# Cleanly stops Helm, Nexus, Core, and Keycloak
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "================================================================"
echo "  HiveMatrix Helm - Stopping All Services"
echo "================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ ! -d "pyenv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    exit 1
fi

source pyenv/bin/activate

echo -e "${BLUE}Stopping services in reverse order...${NC}"
echo ""

# Stop Nexus
echo -e "${YELLOW}[1/3] Stopping Nexus...${NC}"
python cli.py stop nexus 2>/dev/null || echo "  (Nexus may not be running)"

echo ""

# Stop Core
echo -e "${YELLOW}[2/3] Stopping Core...${NC}"
python cli.py stop core 2>/dev/null || echo "  (Core may not be running)"

echo ""

# Stop Keycloak
echo -e "${YELLOW}[3/3] Stopping Keycloak...${NC}"
python cli.py stop keycloak 2>/dev/null || echo "  (Keycloak may not be running)"

echo ""
echo -e "${GREEN}✓ All services stopped${NC}"
echo ""

# Show final status
echo "================================================================"
echo "  Final Service Status"
echo "================================================================"
python cli.py status

echo ""
echo "================================================================"
echo -e "${GREEN}  All HiveMatrix services have been stopped${NC}"
echo "================================================================"
echo ""
