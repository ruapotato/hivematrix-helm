#!/bin/bash
#
# HiveMatrix Auto-start Installation Script
# Installs HiveMatrix as a user systemd service (no root required for services)
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_FILE="$SCRIPT_DIR/hivematrix.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

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

# Create user systemd directory
echo -e "${YELLOW}Creating user systemd service directory...${NC}"
mkdir -p "$USER_SERVICE_DIR"
echo -e "${GREEN}✓ Directory created${NC}"
echo ""

# Copy service file
echo -e "${YELLOW}Installing systemd service...${NC}"
cp "$SERVICE_FILE" "$USER_SERVICE_DIR/hivematrix.service"
echo -e "${GREEN}✓ Service file installed${NC}"
echo ""

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl --user daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"
echo ""

# Enable service
echo -e "${YELLOW}Enabling HiveMatrix service...${NC}"
systemctl --user enable hivematrix.service
echo -e "${GREEN}✓ Service enabled${NC}"
echo ""

# Enable linger (allows service to run without active login)
echo -e "${YELLOW}Enabling user linger (allows service to run at boot)...${NC}"
if loginctl enable-linger "$USER" 2>/dev/null; then
    echo -e "${GREEN}✓ Linger enabled${NC}"
else
    echo -e "${YELLOW}⚠ Could not enable linger (may need sudo)${NC}"
    echo -e "${YELLOW}  Run: sudo loginctl enable-linger $USER${NC}"
fi
echo ""

echo "================================================================"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "================================================================"
echo ""
echo -e "${BLUE}Service Commands:${NC}"
echo "  Start:   systemctl --user start hivematrix"
echo "  Stop:    systemctl --user stop hivematrix"
echo "  Status:  systemctl --user status hivematrix"
echo "  Logs:    journalctl --user -u hivematrix -f"
echo ""
echo -e "${BLUE}Auto-start Status:${NC}"
echo "  Enabled: $(systemctl --user is-enabled hivematrix 2>/dev/null || echo 'unknown')"
echo "  Linger:  $(loginctl show-user "$USER" -p Linger --value 2>/dev/null || echo 'unknown')"
echo ""
echo -e "${YELLOW}Note:${NC} HiveMatrix will now start automatically on boot!"
echo ""
