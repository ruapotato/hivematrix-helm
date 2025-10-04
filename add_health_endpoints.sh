#!/bin/bash
#
# Add health endpoints to all HiveMatrix services
#

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "Adding health endpoints to HiveMatrix services..."
echo ""

# Services to update
SERVICES=("hivematrix-codex" "hivematrix-ledger" "hivematrix-knowledgetree")

for SERVICE in "${SERVICES[@]}"; do
    SERVICE_PATH="/home/david/work/$SERVICE"

    if [ ! -d "$SERVICE_PATH" ]; then
        echo -e "${YELLOW}⚠ $SERVICE not found, skipping${NC}"
        continue
    fi

    # Check if health endpoint already exists
    if grep -q "/health" "$SERVICE_PATH/app/routes.py" 2>/dev/null; then
        echo "  $SERVICE already has health endpoint"
        continue
    fi

    # Add health endpoint to routes.py
    if [ -f "$SERVICE_PATH/app/routes.py" ]; then
        echo "  Adding health endpoint to $SERVICE"

        # Add import if needed
        if ! grep -q "from datetime import datetime" "$SERVICE_PATH/app/routes.py"; then
            sed -i '1i from datetime import datetime' "$SERVICE_PATH/app/routes.py"
        fi

        # Add health endpoint at the end
        cat >> "$SERVICE_PATH/app/routes.py" << 'EOF'

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }
EOF
        echo -e "${GREEN}✓ Health endpoint added to $SERVICE${NC}"
    else
        echo -e "${YELLOW}⚠ routes.py not found in $SERVICE${NC}"
    fi
done

echo ""
echo "Restarting services to apply changes..."
echo ""

cd /home/david/work/hivematrix-helm
source pyenv/bin/activate

for SERVICE in "${SERVICES[@]}"; do
    SERVICE_NAME=$(basename $SERVICE | sed 's/hivematrix-//')
    echo "Restarting $SERVICE_NAME..."
    python cli.py restart $SERVICE_NAME 2>/dev/null || echo "  (not running)"
done

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
