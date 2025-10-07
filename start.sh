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
    # Auto-detect all hivematrix services
    for dir in "$PARENT_DIR"/hivematrix-*; do
        if [ -d "$dir" ]; then
            service_name=$(basename "$dir" | sed 's/^hivematrix-//')
            # Skip core, nexus, helm
            if [[ "$service_name" != "core" ]] && [[ "$service_name" != "nexus" ]] && [[ "$service_name" != "helm" ]]; then
                if [ -f "$dir/run.py" ]; then
                    python cli.py stop $service_name 2>/dev/null || echo "  (already stopped)"
                fi
            fi
        fi
    done

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
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║         Welcome to HiveMatrix Installation!           ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║   This appears to be a fresh installation.            ║${NC}"
echo -e "${CYAN}║   I'll guide you through the setup process.           ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
else
echo -e "${CYAN}Verifying HiveMatrix installation...${NC}"
echo ""
fi

# Always run installation checks, but skip what's already done

# === DEPENDENCY CHECK ===
echo "================================================================"
echo "  Step 1: System Dependencies"
echo "================================================================"
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
. /etc/os-release
OS=$ID
else
OS="unknown"
fi

# Set package manager commands
if [[ "$OS" == "fedora" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "centos" ]]; then
PKG_UPDATE="sudo dnf check-update"
PKG_INSTALL="sudo dnf install -y"
PYTHON_PKG="python3 python3-pip python3-virtualenv"
GIT_PKG="git"
JAVA_PKG="java-17-openjdk-headless"
PG_PKG="postgresql postgresql-server postgresql-contrib postgresql-devel"
WGET_PKG="wget"
elif [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
PKG_UPDATE="sudo apt update"
PKG_INSTALL="sudo apt install -y"
PYTHON_PKG="python3 python3-pip python3-venv"
GIT_PKG="git"
JAVA_PKG="openjdk-17-jre-headless"
PG_PKG="postgresql postgresql-contrib libpq-dev"
WGET_PKG="wget"
else
echo -e "${YELLOW}⚠ Unknown OS: $OS${NC}"
echo "Assuming Debian/Ubuntu package manager..."
PKG_UPDATE="sudo apt update"
PKG_INSTALL="sudo apt install -y"
PYTHON_PKG="python3 python3-pip python3-venv"
GIT_PKG="git"
JAVA_PKG="openjdk-17-jre-headless"
PG_PKG="postgresql postgresql-contrib libpq-dev"
WGET_PKG="wget"
fi

# Check Python
echo -e "${YELLOW}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
echo -e "${RED}✗ Python 3 not found${NC}"
echo "Installing Python 3..."
$PKG_UPDATE
$PKG_INSTALL $PYTHON_PKG
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
echo ""

# Check Git
echo -e "${YELLOW}Checking Git...${NC}"
if ! command -v git &> /dev/null; then
echo -e "${RED}✗ Git not found${NC}"
echo "Installing Git..."
$PKG_INSTALL $GIT_PKG
fi
echo -e "${GREEN}✓ Git installed${NC}"
echo ""

# Check Java (for Keycloak)
echo -e "${YELLOW}Checking Java...${NC}"
if ! command -v java &> /dev/null; then
echo -e "${RED}✗ Java not found${NC}"
echo "Installing OpenJDK 17..."
$PKG_INSTALL $JAVA_PKG
fi
JAVA_VERSION=$(java -version 2>&1 | head -n 1)
echo -e "${GREEN}✓ $JAVA_VERSION${NC}"
echo ""

# Check PostgreSQL
echo -e "${YELLOW}Checking PostgreSQL...${NC}"
if ! command -v psql &> /dev/null; then
echo -e "${RED}✗ PostgreSQL not found${NC}"
echo "Installing PostgreSQL..."
$PKG_INSTALL $PG_PKG

# Initialize PostgreSQL for Fedora/RHEL
if [[ "$OS" == "fedora" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "centos" ]]; then
    if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then
        sudo postgresql-setup --initdb
    fi
fi

sudo systemctl start postgresql
sudo systemctl enable postgresql
fi
PG_VERSION=$(psql --version | awk '{print $3}')
echo -e "${GREEN}✓ PostgreSQL $PG_VERSION${NC}"
echo ""

# Check wget/curl
if ! command -v wget &> /dev/null; then
echo "Installing wget..."
$PKG_INSTALL $WGET_PKG
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

# Load Keycloak version from config file
source "$SCRIPT_DIR/keycloak_version.conf"

if [ ! -d "$PARENT_DIR/keycloak-${KEYCLOAK_VERSION}" ]; then
    echo -e "${YELLOW}Downloading Keycloak ${KEYCLOAK_VERSION}...${NC}"
    cd "$PARENT_DIR"
    wget -q --show-progress https://github.com/keycloak/keycloak/releases/download/${KEYCLOAK_VERSION}/keycloak-${KEYCLOAK_VERSION}.tar.gz
    echo -e "${YELLOW}Extracting Keycloak...${NC}"
    tar -xzf keycloak-${KEYCLOAK_VERSION}.tar.gz
    rm keycloak-${KEYCLOAK_VERSION}.tar.gz

    cd "$SCRIPT_DIR"
    echo -e "${GREEN}✓ Keycloak installed${NC}"
else
    echo -e "${GREEN}✓ Keycloak already installed${NC}"
fi

# Ensure Keycloak is in services.json
if [ -f "services.json" ]; then
    if ! grep -q '"keycloak"' services.json; then
        echo -e "${YELLOW}Adding Keycloak to services.json...${NC}"
        python3 << EOF
import json

with open('services.json', 'r') as f:
    services = json.load(f)

if 'keycloak' not in services:
    # Create new dict with keycloak first
    new_services = {
        'keycloak': {
            'url': 'http://localhost:8080',
            'path': '../keycloak-${KEYCLOAK_VERSION}',
            'port': 8080,
            'type': 'keycloak',
            'start_command': 'bin/kc.sh start-dev'
        }
    }
    # Add all other services
    new_services.update(services)

    with open('services.json', 'w') as f:
        json.dump(new_services, f, indent=2)
EOF
        echo -e "${GREEN}✓ Keycloak added to services.json${NC}"
    fi
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
    deactivate
fi

# Setup setcap for port 443 binding (must happen AFTER venv is created)
echo -e "${YELLOW}Configuring Nexus for HTTPS (port 443)...${NC}"

# Generate SSL certificates if they don't exist
NEXUS_CERT_DIR="$PARENT_DIR/hivematrix-nexus/certs"
mkdir -p "$NEXUS_CERT_DIR"

if [ ! -f "$NEXUS_CERT_DIR/nexus.crt" ] || [ ! -f "$NEXUS_CERT_DIR/nexus.key" ]; then
    echo -e "${YELLOW}  Generating self-signed SSL certificate...${NC}"
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "$NEXUS_CERT_DIR/nexus.key" \
        -out "$NEXUS_CERT_DIR/nexus.crt" \
        -days 365 -subj "/CN=localhost/O=HiveMatrix/C=US" 2>/dev/null
    chmod 600 "$NEXUS_CERT_DIR/nexus.key"
    chmod 644 "$NEXUS_CERT_DIR/nexus.crt"
    echo -e "${GREEN}  ✓ SSL certificate generated${NC}"
else
    echo -e "${GREEN}  ✓ SSL certificate already exists${NC}"
fi

# Get the real Python binary (following symlinks)
NEXUS_VENV_PYTHON="$PARENT_DIR/hivematrix-nexus/pyenv/bin/python3"
if [ -f "$NEXUS_VENV_PYTHON" ]; then
    REAL_PYTHON=$(readlink -f "$NEXUS_VENV_PYTHON")
    echo -e "${YELLOW}  Detected Python: $REAL_PYTHON${NC}"

    # Check if capability is already set
    CURRENT_CAP=$(getcap "$REAL_PYTHON" 2>/dev/null)
    if echo "$CURRENT_CAP" | grep -q "cap_net_bind_service"; then
        echo -e "${GREEN}  ✓ Port 443 binding already enabled${NC}"
    else
        # Check if we need sudo
        if ! sudo -n true 2>/dev/null; then
            echo -e "${YELLOW}  Sudo password required to enable port 443 binding...${NC}"
        fi
        # Grant capability to bind privileged ports on the real binary
        if sudo setcap 'cap_net_bind_service=+ep' "$REAL_PYTHON" 2>/dev/null; then
            echo -e "${GREEN}  ✓ setcap applied to $REAL_PYTHON${NC}"

            # Test if it actually works
            echo -e "${YELLOW}  Testing port 443 binding...${NC}"
            cd "$PARENT_DIR/hivematrix-nexus"
            if timeout 3 "$REAL_PYTHON" -c "import socket; s=socket.socket(); s.bind(('0.0.0.0', 443)); s.close(); print('OK')" 2>/dev/null | grep -q OK; then
                echo -e "${GREEN}  ✓ Port 443 binding test successful${NC}"
            else
                echo -e "${YELLOW}  ✗ Port 443 binding test failed${NC}"
                echo -e "${YELLOW}  Nexus will fall back to port 8000${NC}"
            fi
            cd "$SCRIPT_DIR"
        else
            echo -e "${YELLOW}  ✗ Could not set capabilities (setcap failed)${NC}"
            echo -e "${YELLOW}  Nexus will run on port 8000 instead${NC}"
        fi
    fi
else
    echo -e "${YELLOW}  ✗ Nexus Python binary not found at: $NEXUS_VENV_PYTHON${NC}"
    echo -e "${YELLOW}  Skipping port 443 setup - Nexus will run on port 8000${NC}"
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
set +e  # Disable exit on error temporarily
OUTPUT=$(python cli.py start keycloak 2>&1)
EXIT_CODE=$?
set -e  # Re-enable exit on error

if echo "$OUTPUT" | grep -q "already running"; then
    echo -e "${BLUE}  ✓ Keycloak already running${NC}"
elif [ $EXIT_CODE -eq 0 ] || echo "$OUTPUT" | grep -q "started"; then
    echo -e "${GREEN}✓ Keycloak started${NC}"
    sleep 10
else
    echo -e "${YELLOW}  Keycloak status uncertain, continuing...${NC}"
fi

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

# Disable exit on error for service starts
set +e

# Start Keycloak
echo -e "${YELLOW}[1/3] Starting Keycloak...${NC}"
OUTPUT=$(python cli.py start keycloak 2>&1)
EXIT_CODE=$?
if echo "$OUTPUT" | grep -q "already running"; then
echo -e "${BLUE}  ✓ Service already running${NC}"
elif [ $EXIT_CODE -eq 0 ] || echo "$OUTPUT" | grep -q "started"; then
echo -e "${GREEN}✓ Keycloak started${NC}"
echo "  Waiting for Keycloak to initialize..."
sleep 5
else
echo -e "${RED}✗ Failed to start Keycloak${NC}"
echo "$OUTPUT"
set -e
exit 1
fi

echo ""

# Check and generate JWT keys for Core if needed
echo -e "${YELLOW}Checking Core JWT keys...${NC}"
CORE_KEYS_DIR="$PARENT_DIR/hivematrix-core/keys"
if [ ! -f "$CORE_KEYS_DIR/jwt_private.pem" ] || [ ! -f "$CORE_KEYS_DIR/jwt_public.pem" ]; then
    echo "  Generating JWT keys for Core..."
    mkdir -p "$CORE_KEYS_DIR"
    openssl genrsa -out "$CORE_KEYS_DIR/jwt_private.pem" 2048 2>/dev/null
    openssl rsa -in "$CORE_KEYS_DIR/jwt_private.pem" -pubout -out "$CORE_KEYS_DIR/jwt_public.pem" 2>/dev/null
    chmod 600 "$CORE_KEYS_DIR/jwt_private.pem"
    chmod 644 "$CORE_KEYS_DIR/jwt_public.pem"
    echo -e "${GREEN}  ✓ JWT keys generated${NC}"
else
    echo -e "${BLUE}  ✓ JWT keys exist${NC}"
fi

# Start Core
echo -e "${YELLOW}[2/3] Starting Core...${NC}"
OUTPUT=$(python cli.py start core 2>&1)
EXIT_CODE=$?
if echo "$OUTPUT" | grep -q "already running"; then
echo -e "${BLUE}  ✓ Service already running${NC}"
elif [ $EXIT_CODE -eq 0 ] || echo "$OUTPUT" | grep -q "started"; then
echo -e "${GREEN}✓ Core started${NC}"
echo "  Waiting for Core to initialize..."
sleep 5
else
echo -e "${RED}✗ Failed to start Core${NC}"
echo "$OUTPUT"
set -e
cleanup
fi

echo ""

# Start Nexus
echo -e "${YELLOW}[3/3] Starting Nexus...${NC}"
OUTPUT=$(python cli.py start nexus 2>&1)
EXIT_CODE=$?
if echo "$OUTPUT" | grep -q "already running"; then
echo -e "${BLUE}  ✓ Service already running${NC}"
elif [ $EXIT_CODE -eq 0 ] || echo "$OUTPUT" | grep -q "started"; then
echo -e "${GREEN}✓ Nexus started${NC}"
echo "  Waiting for Nexus to initialize..."
sleep 5
else
echo -e "${RED}✗ Failed to start Nexus${NC}"
echo "$OUTPUT"
set -e
cleanup
fi

# Re-enable exit on error
set -e

echo ""
echo -e "${GREEN}✓ All required services running${NC}"
echo ""

# Auto-detect and start additional services
echo "================================================================"
echo "  Detecting Additional Services"
echo "================================================================"
echo ""

# Find all hivematrix-* directories (excluding core, nexus, helm)
ADDITIONAL_SERVICES=()
for dir in "$PARENT_DIR"/hivematrix-*; do
    if [ -d "$dir" ]; then
        service_name=$(basename "$dir" | sed 's/^hivematrix-//')
        # Skip core, nexus, helm
        if [[ "$service_name" != "core" ]] && [[ "$service_name" != "nexus" ]] && [[ "$service_name" != "helm" ]]; then
            # Check if it has a run.py file (indicates it's a Flask service)
            if [ -f "$dir/run.py" ]; then
                ADDITIONAL_SERVICES+=("$service_name")
                echo -e "${BLUE}  Found: $service_name${NC}"
            fi
        fi
    fi
done

if [ ${#ADDITIONAL_SERVICES[@]} -gt 0 ]; then
    echo ""
    echo "================================================================"
    echo "  Starting Additional Services"
    echo "================================================================"
    echo ""

    for svc in "${ADDITIONAL_SERVICES[@]}"; do
        echo -e "${YELLOW}Starting $svc...${NC}"
        python cli.py start $svc 2>/dev/null || echo "  (already running or failed)"
        sleep 2
    done

    echo ""
    echo -e "${GREEN}✓ Additional services started${NC}"
    echo ""
else
    echo -e "${BLUE}  No additional services found${NC}"
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

# Check if port 5004 is already in use
if lsof -i :5004 > /dev/null 2>&1; then
    echo -e "${YELLOW}Port 5004 is already in use. Checking for stray Helm processes...${NC}"
    STRAY_PIDS=$(lsof -ti :5004 2>/dev/null)
    if [ -n "$STRAY_PIDS" ]; then
        echo "  Stopping stray processes: $STRAY_PIDS"
        kill -9 $STRAY_PIDS 2>/dev/null || true
        sleep 1
        echo -e "${GREEN}  ✓ Stray processes stopped${NC}"
    fi
fi

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
echo -e "  ${BLUE}Login URL:${NC}         ${CYAN}http://localhost:443${NC}"
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
