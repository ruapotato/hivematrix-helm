#!/bin/bash
#
# HiveMatrix Helm - Unified Startup Script
# Starts Keycloak, Core, Nexus, and Helm in the correct order
# Handles Ctrl+C to cleanly shutdown all services
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track PIDs for cleanup
declare -a SERVICE_PIDS=()
HELM_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo ""
    echo "================================================================"
    echo -e "${YELLOW}  Shutting down all services...${NC}"
    echo "================================================================"
    echo ""

    # Stop Helm first if it's running
    if [ -n "$HELM_PID" ]; then
        echo -e "${YELLOW}Stopping Helm...${NC}"
        kill $HELM_PID 2>/dev/null || true
        wait $HELM_PID 2>/dev/null || true
    fi

    # Stop services in reverse order using CLI
    cd "$SCRIPT_DIR"
    source pyenv/bin/activate 2>/dev/null || true

    echo -e "${YELLOW}Stopping additional services...${NC}"
    python cli.py stop knowledgetree 2>/dev/null || echo "  (already stopped)"
    python cli.py stop ledger 2>/dev/null || echo "  (already stopped)"
    python cli.py stop codex 2>/dev/null || echo "  (already stopped)"

    echo -e "${YELLOW}Stopping core services...${NC}"
    python cli.py stop nexus 2>/dev/null || echo "  (already stopped)"
    python cli.py stop core 2>/dev/null || echo "  (already stopped)"
    python cli.py stop keycloak 2>/dev/null || echo "  (already stopped)"

    echo ""
    echo "================================================================"
    echo -e "${GREEN}  All services stopped${NC}"
    echo "================================================================"
    echo ""
    exit 0
}

# Trap Ctrl+C and call cleanup
trap cleanup SIGINT SIGTERM

echo ""
echo "================================================================"
echo "  HiveMatrix Helm - Unified Startup"
echo "================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ ! -d "pyenv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo "  Please run setup first"
    exit 1
fi

source pyenv/bin/activate

echo -e "${BLUE}Starting required services...${NC}"
echo ""

# Start Keycloak
echo -e "${YELLOW}[1/3] Starting Keycloak...${NC}"
OUTPUT=$(python cli.py start keycloak 2>&1)
if echo "$OUTPUT" | grep -q "Service already running"; then
    echo -e "${BLUE}  Service already running${NC}"
elif echo "$OUTPUT" | grep -q "started successfully"; then
    echo -e "${GREEN}✓ Keycloak started${NC}"
    echo "  Waiting for Keycloak to initialize..."
    sleep 5
else
    echo -e "${RED}✗ Failed to start Keycloak${NC}"
    echo "$OUTPUT"
    exit 1
fi

echo ""

# Start Core
echo -e "${YELLOW}[2/3] Starting Core...${NC}"
OUTPUT=$(python cli.py start core 2>&1)
if echo "$OUTPUT" | grep -q "Service already running"; then
    echo -e "${BLUE}  Service already running${NC}"
elif echo "$OUTPUT" | grep -q "started successfully"; then
    echo -e "${GREEN}✓ Core started${NC}"
    echo "  Waiting for Core to initialize..."
    sleep 5
else
    echo -e "${RED}✗ Failed to start Core${NC}"
    echo "$OUTPUT"
    echo ""
    echo -e "${YELLOW}Tip: Make sure Core's .flaskenv file is configured${NC}"
    cleanup
fi

echo ""

# Start Nexus
echo -e "${YELLOW}[3/3] Starting Nexus...${NC}"
OUTPUT=$(python cli.py start nexus 2>&1)
if echo "$OUTPUT" | grep -q "Service already running"; then
    echo -e "${BLUE}  Service already running${NC}"
elif echo "$OUTPUT" | grep -q "started successfully"; then
    echo -e "${GREEN}✓ Nexus started${NC}"
    echo "  Waiting for Nexus to initialize..."
    sleep 5
else
    echo -e "${RED}✗ Failed to start Nexus${NC}"
    echo "$OUTPUT"
    cleanup
fi

echo ""
echo -e "${GREEN}✓ All required services running${NC}"
echo ""

# Start additional services
echo "================================================================"
echo "  Starting Additional Services"
echo "================================================================"
echo ""

echo -e "${YELLOW}Starting Codex...${NC}"
python cli.py start codex 2>/dev/null || echo "  (already running or failed)"
sleep 2

echo -e "${YELLOW}Starting Ledger...${NC}"
python cli.py start ledger 2>/dev/null || echo "  (already running or failed)"
sleep 2

echo -e "${YELLOW}Starting KnowledgeTree...${NC}"
python cli.py start knowledgetree 2>/dev/null || echo "  (already running or failed)"
sleep 2

echo ""
echo -e "${GREEN}✓ Additional services started${NC}"
echo ""

# Show status
echo "================================================================"
echo "  Service Status"
echo "================================================================"
python cli.py status

echo ""
echo "================================================================"
echo "  Starting Helm Web Interface"
echo "================================================================"
echo ""

# Start Helm
python run.py &
HELM_PID=$!

# Wait and check if Helm started successfully
sleep 3

# Check if Helm process is still running
if ! ps -p $HELM_PID > /dev/null 2>&1; then
    echo -e "${RED}✗ Helm failed to start${NC}"
    echo ""
    echo "Check the output above for errors."
    cleanup
fi

echo ""
echo "================================================================"
echo -e "${GREEN}  HiveMatrix is Ready!${NC}"
echo "================================================================"
echo ""
echo -e "  ${BLUE}Nexus (Login):${NC}     http://localhost:8000"
echo -e "  ${BLUE}Helm Dashboard:${NC}    http://localhost:5004"
echo ""
echo "  Keycloak Admin:   http://localhost:8080 (admin/admin)"
echo "  Core Service:     http://localhost:5000"
echo ""
echo "================================================================"
echo ""
echo -e "${YELLOW}To access Helm, visit:${NC}"
echo -e "${GREEN}http://localhost:8000${NC}"
echo ""
echo "You will be redirected to login via Keycloak."
echo "After login, you can access the Helm dashboard."
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo "================================================================"
echo ""

# Wait for Helm process
wait $HELM_PID
