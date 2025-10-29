#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo "================================================================"
echo -e "${YELLOW}  Stopping All HiveMatrix Services${NC}"
echo "================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$SCRIPT_DIR"

# Function to gracefully stop processes
stop_process() {
    local pid=$1
    local name=$2
    local timeout=10

    if [ -z "$pid" ]; then
        return
    fi

    if ! kill -0 $pid 2>/dev/null; then
        return
    fi

    echo -e "${YELLOW}Stopping $name (PID: $pid)...${NC}"

    # Send SIGTERM for graceful shutdown
    kill -TERM $pid 2>/dev/null

    # Wait for process to stop
    local waited=0
    while kill -0 $pid 2>/dev/null && [ $waited -lt $timeout ]; do
        sleep 0.5
        waited=$((waited + 1))
    done

    # Force kill if still running
    if kill -0 $pid 2>/dev/null; then
        echo -e "${RED}  Force killing $name${NC}"
        kill -9 $pid 2>/dev/null
        sleep 0.5
    fi

    echo -e "${GREEN}  ✓ Stopped $name${NC}"
}

# Stop using CLI for services that support it
echo -e "${CYAN}Stopping services via CLI...${NC}"
if [ -f "pyenv/bin/python" ]; then
    source pyenv/bin/activate 2>/dev/null || true

    # Auto-detect and stop all hivematrix services
    for dir in "$PARENT_DIR"/hivematrix-*; do
        if [ -d "$dir" ]; then
            service_name=$(basename "$dir" | sed 's/^hivematrix-//')
            if [ -f "$dir/run.py" ]; then
                python cli.py stop $service_name 2>/dev/null || true
            fi
        fi
    done

    # Stop keycloak
    python cli.py stop keycloak 2>/dev/null || true
fi

sleep 2

# Now kill any remaining HiveMatrix processes
echo ""
echo -e "${CYAN}Cleaning up any remaining processes...${NC}"

# Find all HiveMatrix processes by path
PIDS=$(ps aux | grep -E "hivematrix-(core|nexus|helm|brainhair|codex|knowledgetree|ledger|archive)" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}Found lingering processes:${NC}"
    ps aux | grep -E "hivematrix-(core|nexus|helm|brainhair|codex|knowledgetree|ledger|archive)" | grep -v grep | awk '{print "  PID " $2 ": " $11}'
    echo ""

    for pid in $PIDS; do
        # Get process name for display
        proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
        stop_process $pid "$proc_name"
    done
else
    echo -e "${GREEN}  No lingering processes found${NC}"
fi

# Find and stop Keycloak
echo ""
echo -e "${CYAN}Checking for Keycloak...${NC}"
KEYCLOAK_PID=$(ps aux | grep keycloak | grep java | grep -v grep | awk '{print $2}')
if [ -n "$KEYCLOAK_PID" ]; then
    stop_process $KEYCLOAK_PID "Keycloak"
else
    echo -e "${GREEN}  Keycloak not running${NC}"
fi

# Clean up any gunicorn workers
echo ""
echo -e "${CYAN}Checking for gunicorn workers...${NC}"
GUNICORN_PIDS=$(ps aux | grep gunicorn | grep hivematrix-nexus | grep -v grep | awk '{print $2}')
if [ -n "$GUNICORN_PIDS" ]; then
    for pid in $GUNICORN_PIDS; do
        stop_process $pid "gunicorn worker"
    done
else
    echo -e "${GREEN}  No gunicorn workers running${NC}"
fi

# Clean up PID files
echo ""
echo -e "${CYAN}Cleaning up PID files...${NC}"
if [ -d "pids" ]; then
    for pidfile in pids/*.pid; do
        if [ -f "$pidfile" ]; then
            rm -f "$pidfile"
            echo "  Removed $(basename $pidfile)"
        fi
    done
else
    echo "  No PID directory found"
fi

echo ""
echo "================================================================"
echo -e "${GREEN}  All HiveMatrix Services Stopped${NC}"
echo "================================================================"
echo ""

# Show final verification
REMAINING=$(ps aux | grep -E "hivematrix|keycloak.*java" | grep -v grep | grep -v "stop.sh")
if [ -n "$REMAINING" ]; then
    echo -e "${RED}Warning: Some processes may still be running:${NC}"
    ps aux | grep -E "hivematrix|keycloak.*java" | grep -v grep | grep -v "stop.sh" | head -5
    echo ""
    echo "Run: pkill -f hivematrix  # to force kill all"
else
    echo -e "${GREEN}✓ All services cleanly stopped${NC}"
fi

echo ""
