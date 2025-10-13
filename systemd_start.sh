#!/bin/bash
#
# HiveMatrix systemd start script
# Starts all services and keeps Helm running in foreground for systemd
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "Starting HiveMatrix services..."

# Activate virtual environment
source pyenv/bin/activate

# Start services using CLI
echo "Starting Keycloak..."
python cli.py start keycloak 2>&1 || echo "(already running)"
sleep 3

echo "Starting Core..."
python cli.py start core 2>&1 || echo "(already running)"
sleep 3

echo "Starting Nexus..."
python cli.py start nexus 2>&1 || echo "(already running)"
sleep 3

# Auto-detect and start additional services
for dir in "$SCRIPT_DIR"/../hivematrix-*; do
    if [ -d "$dir" ]; then
        service_name=$(basename "$dir" | sed 's/^hivematrix-//')
        if [[ "$service_name" != "core" ]] && [[ "$service_name" != "nexus" ]] && [[ "$service_name" != "helm" ]]; then
            if [ -f "$dir/run.py" ]; then
                echo "Starting $service_name..."
                python cli.py start "$service_name" 2>&1 || echo "(already running)"
                sleep 2
            fi
        fi
    fi
done

echo "All services started."
echo "Starting Helm web interface (foreground)..."

# Run Helm in foreground for systemd
exec python run.py
