#!/bin/bash
#
# HiveMatrix Helm - Unified Startup & Installation Script
# Handles fresh Ubuntu installations and starts all services
#

set -e  # Exit on error initially

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Track PIDs for cleanup
declare -a SERVICE_PIDS=()
HELM_PID=""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$SCRIPT_DIR"

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
    if [ -f "pyenv/bin/python" ]; then
        source pyenv/bin/activate 2>/dev/null || true

        echo -e "${YELLOW}Stopping additional services...${NC}"
        python cli.py stop knowledgetree 2>/dev/null || echo "  (already stopped)"
        python cli.py stop ledger 2>/dev/null || echo "  (already stopped)"
        python cli.py stop codex 2>/dev/null || echo "  (already stopped)"

        echo -e "${YELLOW}Stopping core services...${NC}"
        python cli.py stop nexus 2>/dev/null || echo "  (already stopped)"
        python cli.py stop core 2>/dev/null || echo "  (already stopped)"
        python cli.py stop keycloak 2>/dev/null || echo "  (already stopped)"
    fi

    echo ""
    echo "================================================================"
    echo -e "${GREEN}  All services stopped${NC}"
    echo "================================================================"
    echo ""
    exit 0
}

# Trap Ctrl+C and call cleanup
trap cleanup SIGINT SIGTERM

# Header
echo ""
echo "================================================================"
echo "  HiveMatrix Helm - Orchestration System"
echo "================================================================"
echo ""

# Check if this is a fresh install
IS_FRESH_INSTALL=false

if [ ! -d "pyenv" ] || [ ! -f "instance/helm.conf" ]; then
    IS_FRESH_INSTALL=true
fi

if [ "$IS_FRESH_INSTALL" = true ]; then
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}║         Welcome to HiveMatrix Installation!           ║${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}║   This appears to be a fresh installation.            ║${NC}"
    echo -e "${CYAN}║   I'll guide you through the setup process.           ║${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This installer will:"
    echo "  1. Check and install system dependencies"
    echo "  2. Download and setup Keycloak"
    echo "  3. Clone Core and Nexus (required components)"
    echo "  4. Setup PostgreSQL databases"
    echo "  5. Configure authentication"
    echo "  6. Start all services"
    echo ""
    read -p "Continue with installation? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi
    echo ""

    # === DEPENDENCY CHECK ===
    echo "================================================================"
    echo "  Step 1: System Dependencies"
    echo "================================================================"
    echo ""

    # Check Python
    echo -e "${YELLOW}Checking Python...${NC}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found${NC}"
        echo "Installing Python 3..."
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv
    fi
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
    echo ""

    # Check Git
    echo -e "${YELLOW}Checking Git...${NC}"
    if ! command -v git &> /dev/null; then
        echo -e "${RED}✗ Git not found${NC}"
        echo "Installing Git..."
        sudo apt install -y git
    fi
    echo -e "${GREEN}✓ Git installed${NC}"
    echo ""

    # Check Java (for Keycloak)
    echo -e "${YELLOW}Checking Java...${NC}"
    if ! command -v java &> /dev/null; then
        echo -e "${RED}✗ Java not found${NC}"
        echo "Installing OpenJDK 17..."
        sudo apt install -y openjdk-17-jre-headless
    fi
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    echo -e "${GREEN}✓ $JAVA_VERSION${NC}"
    echo ""

    # Check PostgreSQL
    echo -e "${YELLOW}Checking PostgreSQL...${NC}"
    if ! command -v psql &> /dev/null; then
        echo -e "${RED}✗ PostgreSQL not found${NC}"
        echo "Installing PostgreSQL..."
        sudo apt install -y postgresql postgresql-contrib libpq-dev
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    PG_VERSION=$(psql --version | awk '{print $3}')
    echo -e "${GREEN}✓ PostgreSQL $PG_VERSION${NC}"
    echo ""

    # Check wget/curl
    if ! command -v wget &> /dev/null; then
        echo "Installing wget..."
        sudo apt install -y wget
    fi

    echo -e "${GREEN}✓ All system dependencies ready${NC}"
    echo ""

    # === SETUP HELM ===
    echo "================================================================"
    echo "  Step 2: Setup Helm"
    echo "================================================================"
    echo ""

    echo -e "${YELLOW}Creating Helm virtual environment...${NC}"
    python3 -m venv pyenv
    source pyenv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Helm environment ready${NC}"
    echo ""

    # === DOWNLOAD KEYCLOAK ===
    echo "================================================================"
    echo "  Step 3: Setup Keycloak"
    echo "================================================================"
    echo ""

    if [ ! -d "$PARENT_DIR/keycloak-26.0.5" ]; then
        echo -e "${YELLOW}Downloading Keycloak 26.0.5...${NC}"
        cd "$PARENT_DIR"
        wget -q --show-progress https://github.com/keycloak/keycloak/releases/download/26.0.5/keycloak-26.0.5.tar.gz
        echo -e "${YELLOW}Extracting Keycloak...${NC}"
        tar -xzf keycloak-26.0.5.tar.gz
        rm keycloak-26.0.5.tar.gz
        cd "$SCRIPT_DIR"
        echo -e "${GREEN}✓ Keycloak installed${NC}"
    else
        echo -e "${GREEN}✓ Keycloak already installed${NC}"
    fi
    echo ""

    # === CLONE CORE AND NEXUS ===
    echo "================================================================"
    echo "  Step 4: Clone Required Components"
    echo "================================================================"
    echo ""

    # Clone Core
    if [ ! -d "$PARENT_DIR/hivematrix-core" ]; then
        echo -e "${YELLOW}Cloning HiveMatrix Core...${NC}"
        cd "$PARENT_DIR"
        git clone https://github.com/ruapotato/hivematrix-core
        cd "$SCRIPT_DIR"
        echo -e "${GREEN}✓ Core cloned${NC}"
    else
        echo -e "${GREEN}✓ Core already exists${NC}"
    fi
    echo ""

    # Clone Nexus
    if [ ! -d "$PARENT_DIR/hivematrix-nexus" ]; then
        echo -e "${YELLOW}Cloning HiveMatrix Nexus...${NC}"
        cd "$PARENT_DIR"
        git clone https://github.com/ruapotato/hivematrix-nexus
        cd "$SCRIPT_DIR"
        echo -e "${GREEN}✓ Nexus cloned${NC}"
    else
        echo -e "${GREEN}✓ Nexus already exists${NC}"
    fi
    echo ""

    # === INSTALL CORE AND NEXUS ===
    echo "================================================================"
    echo "  Step 5: Install Core and Nexus"
    echo "================================================================"
    echo ""

    # Install Core
    echo -e "${YELLOW}Installing Core...${NC}"
    cd "$PARENT_DIR/hivematrix-core"
    if [ -f "install.sh" ]; then
        chmod +x install.sh
        ./install.sh
    else
        python3 -m venv pyenv
        source pyenv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    cd "$SCRIPT_DIR"
    echo -e "${GREEN}✓ Core installed${NC}"
    echo ""

    # Install Nexus
    echo -e "${YELLOW}Installing Nexus...${NC}"
    cd "$PARENT_DIR/hivematrix-nexus"
    if [ -f "install.sh" ]; then
        chmod +x install.sh
        ./install.sh
    else
        python3 -m venv pyenv
        source pyenv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    cd "$SCRIPT_DIR"
    echo -e "${GREEN}✓ Nexus installed${NC}"
    echo ""

    # === SETUP DATABASES ===
    echo "================================================================"
    echo "  Step 6: Database Setup"
    echo "================================================================"
    echo ""

    echo "We need to setup PostgreSQL databases for Helm, Core, and other services."
    echo ""
    echo -e "${YELLOW}Setting up Helm database...${NC}"

    # Initialize Helm database
    source pyenv/bin/activate
    if [ ! -f "instance/helm.conf" ]; then
        python init_db.py
    fi
    echo -e "${GREEN}✓ Helm database ready${NC}"
    echo ""

    # === UPDATE SERVICES CONFIG ===
    echo "================================================================"
    echo "  Step 7: Configure Services"
    echo "================================================================"
    echo ""

    echo -e "${YELLOW}Updating service registry...${NC}"
    python install_manager.py update-config
    echo -e "${GREEN}✓ Services configured${NC}"
    echo ""

    # === SETUP KEYCLOAK ===
    echo "================================================================"
    echo "  Step 8: Configure Keycloak"
    echo "================================================================"
    echo ""

    echo -e "${YELLOW}Starting Keycloak for configuration...${NC}"
    python cli.py start keycloak
    sleep 10

    echo -e "${YELLOW}Configuring Keycloak realm and users...${NC}"
    if [ -f "configure_keycloak.sh" ]; then
        chmod +x configure_keycloak.sh
        ./configure_keycloak.sh
    fi
    echo -e "${GREEN}✓ Keycloak configured${NC}"
    echo ""

    # === INSTALLATION COMPLETE ===
    echo "================================================================"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo "================================================================"
    echo ""
    echo -e "${CYAN}Default Credentials:${NC}"
    echo -e "  Username: ${GREEN}admin${NC}"
    echo -e "  Password: ${GREEN}admin${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT: Change the default password after first login!${NC}"
    echo ""
    echo "Starting services..."
    echo ""
fi

# === START SERVICES ===
# Activate virtual environment
if [ ! -d "pyenv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo "  Please run the installation first"
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

# Start additional services if they exist
ADDITIONAL_SERVICES=("codex" "ledger" "knowledgetree")
HAS_ADDITIONAL=false

for svc in "${ADDITIONAL_SERVICES[@]}"; do
    if [ -d "$PARENT_DIR/hivematrix-$svc" ]; then
        HAS_ADDITIONAL=true
        break
    fi
done

if [ "$HAS_ADDITIONAL" = true ]; then
    echo "================================================================"
    echo "  Starting Additional Services"
    echo "================================================================"
    echo ""

    for svc in "${ADDITIONAL_SERVICES[@]}"; do
        if [ -d "$PARENT_DIR/hivematrix-$svc" ]; then
            echo -e "${YELLOW}Starting $svc...${NC}"
            python cli.py start $svc 2>/dev/null || echo "  (already running or failed)"
            sleep 2
        fi
    done

    echo ""
    echo -e "${GREEN}✓ Additional services started${NC}"
    echo ""
fi

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
echo -e "  ${BLUE}Login URL:${NC}         ${CYAN}http://localhost:8000${NC}"
echo -e "  ${BLUE}Helm Dashboard:${NC}    http://localhost:5004"
echo ""
echo -e "  ${YELLOW}Default Login:${NC}"
echo -e "    Username: ${GREEN}admin${NC}"
echo -e "    Password: ${GREEN}admin${NC}"
echo ""
echo "  Keycloak Admin:   http://localhost:8080 (admin/admin)"
echo "  Core Service:     http://localhost:5000"
echo ""
echo "================================================================"
echo ""
if [ "$IS_FRESH_INSTALL" = true ]; then
    echo -e "${YELLOW}IMPORTANT SECURITY STEPS:${NC}"
    echo ""
    echo "  1. Login to Keycloak admin console:"
    echo "     http://localhost:8080"
    echo ""
    echo "  2. Go to: hivematrix realm → Users → admin"
    echo ""
    echo "  3. Click 'Credentials' tab"
    echo ""
    echo "  4. Set a new password and mark it as permanent"
    echo ""
    echo "================================================================"
    echo ""
fi
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo "================================================================"
echo ""

# Wait for Helm process
wait $HELM_PID
