# HiveMatrix - Quick Start Guide

## Fresh Ubuntu 24.04 Installation

### Prerequisites
- Fresh Ubuntu 24.04 system (VM, container, or bare metal)
- Internet connection
- Sudo privileges

### One-Command Install

```bash
# Step 1: Create working directory
mkdir -p ~/work && cd ~/work

# Step 2: Install git (if not already installed)
sudo apt update && sudo apt install -y git

# Step 3: Clone Helm
git clone https://github.com/ruapotato/hivematrix-helm
cd hivematrix-helm

# Step 4: Run the installer (handles everything automatically)
./start.sh
```

### What Happens Automatically

The `start.sh` script will:

1. **Detect fresh installation** and guide you through setup
2. **Install system dependencies:**
   - Python 3
   - Git
   - Java 17 (for Keycloak)
   - PostgreSQL
   - wget

3. **Download and setup Keycloak:**
   - Downloads Keycloak 26.0.5
   - Extracts to `../keycloak-26.0.5`
   - Configures admin credentials

4. **Clone required components:**
   - HiveMatrix Core (authentication)
   - HiveMatrix Nexus (frontend gateway)

5. **Install dependencies:**
   - Creates Python virtual environments
   - Installs all Python packages
   - Sets up databases

6. **Configure Keycloak:**
   - Creates `hivematrix` realm
   - Creates `core-client`
   - Sets up admin user and groups
   - Saves client secret to Core

7. **Start all services:**
   - Keycloak on port 8080
   - Core on port 5000
   - Nexus on port 8000
   - Helm on port 5004

8. **Display login information:**
   - Login URL: http://localhost:8000
   - Username: admin
   - Password: admin

### First Login

1. Open browser to: **http://localhost:8000**
2. You'll be redirected to Keycloak login
3. Enter:
   - Username: **admin**
   - Password: **admin**
4. You'll be logged into HiveMatrix

### IMPORTANT: Change Default Password

After first login, immediately change the default password:

1. Go to: **http://localhost:8080**
2. Click "Administration Console"
3. Login with admin/admin
4. Select "hivematrix" realm (top left dropdown)
5. Go to: Users → admin
6. Click "Credentials" tab
7. Set a new password
8. Uncheck "Temporary"
9. Click "Set Password"

## Installing Additional Apps

### Via Web UI

1. Navigate to: **http://localhost:5004/apps**
2. View available apps in the "Available Applications" section
3. Click **"Install"** on any app you want:
   - **Codex** - Central data hub for MSP operations
   - **Ledger** - Billing and invoicing
   - **KnowledgeTree** - Knowledge management with Neo4j
4. Wait for installation to complete
5. Go back to main dashboard: **http://localhost:5004**
6. Click **"Start"** on the newly installed app

### Via Command Line

```bash
cd ~/work/hivematrix-helm

# Install Codex (data hub)
python install_manager.py install codex

# Install Ledger (billing)
python install_manager.py install ledger

# Install KnowledgeTree (knowledge base)
python install_manager.py install knowledgetree

# Update services registry
python install_manager.py update-config

# Start the apps
python cli.py start codex
python cli.py start ledger
python cli.py start knowledgetree
```

### Install Custom App from Git

**Via Web UI:**
1. Go to: http://localhost:5004/apps
2. Click "Install from Git" tab
3. Enter:
   - Git URL: https://github.com/user/repo
   - App Name: myapp
   - Port: 5099
4. Click "Install from Git"

**Via Command Line:**
```bash
# Not yet supported - use web UI
```

## Managing Apps

### Check App Status

```bash
cd ~/work/hivematrix-helm

# Check all installed apps
python install_manager.py list-installed

# Check specific app (includes git status)
python install_manager.py status codex
```

### Update Apps

**Via Web UI:**
1. Go to: http://localhost:5004/apps
2. See "Updates" column showing available updates
3. Click **"Update"** to pull latest changes

**Via Command Line:**
```bash
cd ~/work/hivematrix-helm

# Pull latest changes
python install_manager.py pull codex

# Restart the app
python cli.py restart codex
```

### Configuration

All app configuration is managed centrally by Helm:

```bash
cd ~/work/hivematrix-helm

# View app configuration
python config_manager.py get codex

# Update app configuration (JSON format)
python config_manager.py set codex '{
  "freshservice_api_key": "your-api-key",
  "datto_api_key": "your-api-key"
}'

# Sync configuration to app directory
python config_manager.py write-dotenv codex
python config_manager.py write-conf codex

# Restart app to apply changes
python cli.py restart codex
```

## Service Management

### Start/Stop Services

**Via Web UI:**
- Main dashboard: http://localhost:5004
- Click "Start", "Stop", or "Restart" buttons

**Via Command Line:**
```bash
cd ~/work/hivematrix-helm

# Start a service
python cli.py start codex

# Stop a service
python cli.py stop codex

# Restart a service
python cli.py restart codex

# Check status of all services
python cli.py status
```

### Unified Startup

Use `start.sh` to start everything:

```bash
cd ~/work/hivematrix-helm
./start.sh

# Press Ctrl+C to stop all services gracefully
```

## System URLs

- **Nexus (Login):** http://localhost:8000
- **Helm Dashboard:** http://localhost:5004
- **Core Service:** http://localhost:5000
- **Keycloak Admin:** http://localhost:8080
- **Codex:** http://localhost:5010 (if installed)
- **KnowledgeTree:** http://localhost:5020 (if installed)
- **Ledger:** http://localhost:5030 (if installed)

## Directory Structure

```
~/work/
├── hivematrix-helm/              ← Main orchestrator
├── hivematrix-core/              ← Auto-cloned
├── hivematrix-nexus/             ← Auto-cloned
├── hivematrix-codex/             ← Optional, install via UI/CLI
├── hivematrix-ledger/            ← Optional, install via UI/CLI
├── hivematrix-knowledgetree/     ← Optional, install via UI/CLI
└── keycloak-26.0.5/              ← Auto-downloaded
```

## Troubleshooting

### Services Won't Start

```bash
# Check system dependencies
python install_manager.py check-deps

# View service logs
python cli.py status

# Check specific service
cd ~/work/hivematrix-codex
cat logs/stdout.log
cat logs/stderr.log
```

### Database Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL if stopped
sudo systemctl start postgresql

# Setup database for an app
python config_manager.py setup-db codex
```

### Keycloak Issues

```bash
# Check if Keycloak is running
curl http://localhost:8080

# Restart Keycloak
python cli.py restart keycloak

# Reconfigure Keycloak
./configure_keycloak.sh
```

### Port Already in Use

```bash
# Find what's using a port
sudo lsof -i :5000

# Kill the process
sudo kill -9 <PID>
```

## Next Steps

1. **Configure external APIs** (if using Codex):
   - Freshservice API key
   - Datto RMM API credentials

2. **Setup billing** (if using Ledger):
   - Configure billing plans
   - Add client overrides

3. **Import knowledge** (if using KnowledgeTree):
   - Sync from Codex
   - Add documentation

4. **Customize Keycloak:**
   - Add more users
   - Configure groups
   - Setup SSO

## Getting Help

- **Helm Logs:** http://localhost:5004/logs
- **App Management:** http://localhost:5004/apps
- **Service Status:** `python cli.py status`
- **Documentation:** See README.md and REFACTOR_SUMMARY.md
- **GitHub Issues:** https://github.com/ruapotato/hivematrix-helm/issues

## Security Checklist

- [ ] Change default Keycloak admin password
- [ ] Change default HiveMatrix admin password
- [ ] Set strong PostgreSQL passwords
- [ ] Configure firewall (ufw)
- [ ] Enable HTTPS in production
- [ ] Regular backups
- [ ] Update all components regularly

## Production Deployment

For production deployment, see:
- `README.md` - Full documentation
- `REFACTOR_SUMMARY.md` - Architecture details
- Production section in README for:
  - Systemd service files
  - Nginx reverse proxy
  - SSL/TLS configuration
  - Database backups
  - Log retention

---

**That's it! You now have a fully functional HiveMatrix installation.**

For detailed documentation, see:
- `README.md` - Complete documentation
- `REFACTOR_SUMMARY.md` - Refactor details and migration guide
- `ARCHITECTURE.md` - System architecture
