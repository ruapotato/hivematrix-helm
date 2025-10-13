#!/bin/bash
#
# HiveMatrix systemd stop script
# Stops all HiveMatrix services gracefully
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Stopping HiveMatrix services..."

# Activate virtual environment
source pyenv/bin/activate 2>/dev/null || true

# Stop additional services first
for dir in "$SCRIPT_DIR"/../hivematrix-*; do
    if [ -d "$dir" ]; then
        service_name=$(basename "$dir" | sed 's/^hivematrix-//')
        if [[ "$service_name" != "core" ]] && [[ "$service_name" != "nexus" ]] && [[ "$service_name" != "helm" ]]; then
            if [ -f "$dir/run.py" ]; then
                echo "Stopping $service_name..."
                python cli.py stop "$service_name" 2>/dev/null || true
            fi
        fi
    fi
done

# Stop core services
echo "Stopping Nexus..."
python cli.py stop nexus 2>/dev/null || true

echo "Stopping Core..."
python cli.py stop core 2>/dev/null || true

echo "Stopping Keycloak..."
python cli.py stop keycloak 2>/dev/null || true

echo "All services stopped."
