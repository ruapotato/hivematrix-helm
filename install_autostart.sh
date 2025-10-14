#!/bin/bash
#
# HiveMatrix Auto-start Installation Script
# Installs HiveMatrix as a system service with capability to bind to port 443
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_FILE="$SCRIPT_DIR/hivematrix.service"
SYSTEM_SERVICE_DIR="/etc/systemd/system"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "================================================================"
echo "  HiveMatrix Auto-Start Installation"
echo "================================================================"
echo ""

# Check if initial setup has been done
if [ ! -d "$SCRIPT_DIR/pyenv" ] || [ ! -f "$SCRIPT_DIR/instance/helm.conf" ]; then
    echo -e "${YELLOW}⚠️  Initial setup not detected!${NC}"
    echo ""
    echo "Please run './start.sh' once before installing the systemd service."
    echo "This is required to:"
    echo "  - Install system dependencies (PostgreSQL, Java, etc.)"
    echo "  - Set up port 443 binding capability"
    echo "  - Configure databases and Keycloak"
    echo ""
    echo "After start.sh completes successfully, press Ctrl+C and run this script again."
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Initial setup detected${NC}"
echo ""

# Check for sudo access
echo -e "${YELLOW}Checking for sudo privileges...${NC}"
if ! sudo -v; then
    echo -e "${YELLOW}⚠️ This installation requires sudo access to install the system service${NC}"
    echo ""
    echo "Please run with sudo privileges or provide your password when prompted."
    exit 1
fi
echo -e "${GREEN}✓ Sudo access confirmed${NC}"
echo ""

# Generate service file with correct paths and user
echo -e "${YELLOW}Generating systemd service file...${NC}"
sudo tee "$SYSTEM_SERVICE_DIR/hivematrix.service" > /dev/null <<EOF
[Unit]
Description=HiveMatrix Orchestration System
Documentation=https://github.com/ruapotato/hivematrix-helm
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$(id -gn)
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/systemd_start.sh
ExecStop=$SCRIPT_DIR/systemd_stop.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Capability for binding to privileged ports (< 1024)
AmbientCapabilities=CAP_NET_BIND_SERVICE
# Critical: PrivateUsers must be false for capabilities to work
PrivateUsers=false

# Security hardening (relaxed for development)
PrivateTmp=yes
NoNewPrivileges=true

# Environment
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin"
Environment="HIVEMATRIX_DEV_MODE=false"

[Install]
WantedBy=multi-user.target
EOF
echo -e "${GREEN}✓ Service file generated${NC}"
echo ""

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
sudo systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"
echo ""

# Enable service
echo -e "${YELLOW}Enabling HiveMatrix service...${NC}"
sudo systemctl enable hivematrix.service
echo -e "${GREEN}✓ Service enabled${NC}"
echo ""

echo "================================================================"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "================================================================"
echo ""
echo -e "${BLUE}Service Commands:${NC}"
echo "  Start:   sudo systemctl start hivematrix"
echo "  Stop:    sudo systemctl stop hivematrix"
echo "  Status:  sudo systemctl status hivematrix"
echo "  Logs:    sudo journalctl -u hivematrix -f"
echo ""
echo -e "${BLUE}Auto-start Status:${NC}"
echo "  Enabled: $(sudo systemctl is-enabled hivematrix 2>/dev/null || echo 'unknown')"
echo ""
echo -e "${YELLOW}Note:${NC} HiveMatrix will now start automatically on boot!"
echo ""
echo -e "${YELLOW}To start the service now:${NC}"
echo "  sudo systemctl start hivematrix"
echo ""
