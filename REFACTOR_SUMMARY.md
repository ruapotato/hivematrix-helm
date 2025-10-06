# HiveMatrix Helm - Giant Refactor Summary

## Overview

HiveMatrix has been completely refactored into a unified orchestration system with Helm as the central hub. The system now supports:

- **One-command installation** on fresh Ubuntu 24.04 systems
- **Automatic dependency management** (PostgreSQL, Neo4j, Keycloak, Java, Python)
- **Web-based app installation** from a curated registry or custom git URLs
- **Centralized configuration** - all apps get their settings from Helm
- **Git operations** - pull updates, check status for each module
- **Fresh install detection** - automatically sets up everything on first run

## Key Changes

### 1. App Registry System (`apps_registry.json`)

Centralized registry of all available HiveMatrix applications:

**Core Apps (Required):**
- `core` - Authentication & service registry
- `nexus` - Frontend gateway

**Default Apps (Optional):**
- `codex` - Central data hub for MSP operations
- `ledger` - Billing calculations and invoicing
- `knowledgetree` - Knowledge management with Neo4j

**System Dependencies:**
- `keycloak` - Authentication server (auto-downloaded)
- `postgresql` - Relational database (auto-installed)
- `neo4j` - Graph database (optional, for KnowledgeTree)

### 2. Installation Manager (`install_manager.py`)

Handles all app installation and dependency management:

**Functions:**
- `check_system_dependencies()` - Verify what's installed
- `install_system_dependency(dep_name)` - Auto-install PostgreSQL, Keycloak, Neo4j
- `clone_app(app_key)` - Clone app from git repository
- `install_app(app_key)` - Clone + run install.sh
- `get_app_status(app_key)` - Get git status, branch, updates available
- `git_pull_app(app_key)` - Pull latest changes
- `update_services_json()` - Update service registry

**Usage:**
```bash
python install_manager.py check-deps
python install_manager.py install core
python install_manager.py pull codex
python install_manager.py list-installed
```

### 3. Configuration Manager (`config_manager.py`)

Centralized configuration for all HiveMatrix applications:

**What it manages:**
- System-wide settings (environment, log level, secret keys)
- Keycloak configuration (URL, realm, client ID)
- Database connections (PostgreSQL, Neo4j)
- App-specific configuration
- Auto-generates `.flaskenv` and `instance/app.conf` for each app

**Functions:**
- `get_app_config(app_name)` - Get configuration for an app
- `set_app_config(app_name, config)` - Set app configuration
- `write_app_dotenv(app_name)` - Generate .flaskenv
- `write_app_conf(app_name)` - Generate instance/app.conf
- `sync_all_apps()` - Sync config to all installed apps
- `setup_app_database(app_name)` - Create PostgreSQL database for app

**Usage:**
```bash
python config_manager.py get core
python config_manager.py setup-db codex
python config_manager.py sync-all
```

### 4. Unified Startup Script (`start.sh.new`)

**Fresh Install Detection:**
- Detects if this is a first-time installation
- Automatically installs all system dependencies
- Downloads and configures Keycloak
- Clones Core and Nexus
- Sets up PostgreSQL databases
- Provides default credentials

**Normal Startup:**
- Starts required services (Keycloak, Core, Nexus)
- Starts optional services if installed
- Displays login URL and credentials
- Handles graceful shutdown with Ctrl+C

**Usage:**
```bash
# On fresh Ubuntu 24.04 install:
git clone https://github.com/ruapotato/hivematrix-helm
cd hivematrix-helm
./start.sh

# It will automatically:
# 1. Check/install Python, Git, Java, PostgreSQL
# 2. Download Keycloak
# 3. Clone Core and Nexus
# 4. Setup databases
# 5. Configure authentication
# 6. Start everything
# 7. Show login URL
```

### 5. Web-Based App Management

New `/apps` page in Helm dashboard provides:

**System Dependencies Tab:**
- Check which dependencies are installed
- One-click install for missing dependencies

**Installed Apps Tab:**
- View all installed applications
- Git status (clean/modified)
- Branch information
- Update notifications (commits behind)
- One-click git pull
- Configuration management

**Available Apps Tabs:**
- Core Apps - Required components
- Default Apps - Optional HiveMatrix modules
- Install from Git - Custom repositories

**Features:**
- Install apps with one click
- Pull updates from git
- View and edit app configurations
- Check git status for each app
- Install custom apps from any git URL

**API Endpoints:**
```
GET  /api/apps/registry                 - Get app registry
GET  /api/apps/available                - List available apps
GET  /api/apps/installed                - List installed apps
POST /api/apps/{app}/install            - Install an app
POST /api/apps/{app}/git/pull           - Pull updates
GET  /api/apps/{app}/status             - Get app status
POST /api/apps/install-from-git         - Install from custom URL
GET  /api/dependencies/check            - Check dependencies
POST /api/dependencies/{dep}/install    - Install dependency
```

### 6. Individual App Install Scripts

Template install script (`templates/install.sh`) for each repository:

**What it does:**
- Checks Python version
- Creates virtual environment
- Installs dependencies from requirements.txt
- Creates instance directory
- Runs app-specific setup
- Provides next steps

**Each repository should have:**
- `install.sh` - Installation script
- `requirements.txt` - Python dependencies
- `run.py` - Main application entry point
- `.flaskenv` - Environment variables (auto-generated by Helm)
- `instance/` - Configuration directory (auto-managed by Helm)

### 7. Architecture Changes

**Before:**
```
Each app:
- Manual installation
- Own configuration files
- Independent startup
- Manual git updates
```

**After:**
```
Helm Orchestrator:
├── App Registry (apps_registry.json)
├── Install Manager (install_manager.py)
├── Config Manager (config_manager.py)
├── Unified Start Script (start.sh)
└── Web Management Panel (/apps)
    ├── Install/uninstall apps
    ├── Git operations
    ├── Configuration sync
    └── Dependency management

Apps (hivematrix-*):
├── install.sh (provided by Helm template)
├── Configuration (managed by Helm)
└── Auto-discovered by Helm
```

## Installation Workflow

### Fresh Ubuntu 24.04 System

```bash
# 1. Clone Helm (only thing you need to do manually)
cd /home/user/work
git clone https://github.com/ruapotato/hivematrix-helm
cd hivematrix-helm

# 2. Run start script - it handles EVERYTHING
./start.sh

# The script will:
# - Detect fresh installation
# - Ask for confirmation
# - Install Python, Git, Java, PostgreSQL
# - Download Keycloak 26.0.5
# - Clone Core and Nexus to ../
# - Install all dependencies
# - Setup databases
# - Configure Keycloak with default users
# - Start all services
# - Show login URL

# 3. Access the system
# Open browser to: http://localhost:8000
# Login: admin / admin
```

### Installing Additional Apps

**Via Web UI:**
1. Navigate to http://localhost:5004/apps
2. Browse available apps
3. Click "Install" on desired app
4. Wait for installation to complete
5. Start the app from the main dashboard

**Via CLI:**
```bash
cd hivematrix-helm
python install_manager.py install codex
python install_manager.py install ledger
python install_manager.py install knowledgetree
```

**From Custom Git URL:**
1. Go to /apps page
2. Click "Install from Git" tab
3. Enter:
   - Git URL: https://github.com/user/repo
   - App Name: myapp
   - Port: 5099
4. Click "Install from Git"

## Configuration Management

All configuration is centralized in Helm. Apps get their configuration automatically.

**Example: Adding API keys to Codex**

```bash
cd hivematrix-helm

# Update Codex configuration
python config_manager.py set codex '{
  "freshservice_api_key": "your-key",
  "datto_api_key": "your-key",
  "db_name": "codex_db",
  "db_user": "codex_user"
}'

# Sync to Codex directory
python config_manager.py write-dotenv codex
python config_manager.py write-conf codex

# Restart Codex to pick up changes
python cli.py restart codex
```

## Git Operations

**Check for updates:**
```bash
python install_manager.py status codex
```

**Pull updates:**
```bash
python install_manager.py pull codex
python cli.py restart codex
```

**Via Web UI:**
1. Go to /apps page
2. See "Updates" column showing commits behind
3. Click "Update" button
4. Service will be restarted automatically

## Keycloak Auto-Setup

The `configure_keycloak.sh` script automatically:
- Creates `hivematrix` realm
- Creates `core-client` with proper settings
- Retrieves and saves client secret
- Creates `admins` group
- Configures group mapper
- Creates default admin user (admin/admin)
- Saves configuration to Core's `.flaskenv`

**Security Note:**
After first login, you MUST:
1. Go to http://localhost:8080
2. Login as admin/admin
3. Navigate to hivematrix realm → Users → admin
4. Change the password to something secure

## Directory Structure

```
/home/user/work/
├── hivematrix-helm/              ← Main orchestrator
│   ├── apps_registry.json        ← Available apps
│   ├── install_manager.py        ← App installation
│   ├── config_manager.py         ← Configuration management
│   ├── start.sh                  ← Unified startup
│   ├── services.json             ← Service registry (auto-generated)
│   ├── master_services.json      ← Master service list
│   ├── instance/
│   │   └── configs/
│   │       └── master_config.json  ← Centralized config
│   ├── templates/
│   │   └── install.sh            ← Template for app installers
│   └── app/
│       ├── templates/
│       │   └── apps.html         ← App management UI
│       └── app_manager_routes.py ← App management API
│
├── hivematrix-core/              ← Auto-cloned on first run
├── hivematrix-nexus/             ← Auto-cloned on first run
├── hivematrix-codex/             ← Install via web UI or CLI
├── hivematrix-ledger/            ← Install via web UI or CLI
├── hivematrix-knowledgetree/     ← Install via web UI or CLI
└── keycloak-26.0.5/              ← Auto-downloaded on first run
```

## File Locations

**Helm manages all configuration:**
- `hivematrix-helm/instance/configs/master_config.json` - Master configuration
- `hivematrix-helm/apps_registry.json` - Available apps registry
- `hivematrix-helm/services.json` - Service registry (auto-updated)

**App-specific (auto-generated by Helm):**
- `hivematrix-{app}/.flaskenv` - Environment variables
- `hivematrix-{app}/instance/{app}.conf` - App configuration

## Breaking Changes

### For Existing Installations

1. **Configuration Files:**
   - Old: Each app had its own .flaskenv
   - New: Generated by Helm from master config
   - **Action:** Run `config_manager.py sync-all`

2. **Service Registry:**
   - Old: Manually edit services.json in each app
   - New: Auto-generated by Helm
   - **Action:** Run `install_manager.py update-config`

3. **Startup Process:**
   - Old: Start each service individually
   - New: Use `start.sh` or Helm dashboard
   - **Action:** Use new startup script

### For App Developers

Each app repository should now include:

1. **install.sh** - Based on template in helm/templates/
2. **Dependency on Helm** - Apps get config from Helm
3. **No hardcoded credentials** - Everything from config
4. **Health endpoint** - Implement `/health` for monitoring

## Testing the New System

### Test Fresh Install

```bash
# On a fresh Ubuntu 24.04 VM or container
sudo apt update
sudo apt install -y git

# Clone and start
cd ~
mkdir work
cd work
git clone https://github.com/ruapotato/hivematrix-helm
cd hivematrix-helm
./start.sh

# Follow prompts
# System should auto-install everything
# Login at http://localhost:8000
```

### Test App Installation

```bash
# Via CLI
python install_manager.py install codex

# Via Web
# 1. Go to http://localhost:5004/apps
# 2. Click Install on Codex
# 3. Wait for completion
# 4. Start from main dashboard
```

### Test Configuration Sync

```bash
# Update config
python config_manager.py set codex '{"test_key": "test_value"}'

# Sync to app
python config_manager.py write-dotenv codex
python config_manager.py write-conf codex

# Verify
cat ../hivematrix-codex/.flaskenv
cat ../hivematrix-codex/instance/codex.conf
```

## Migration Guide

### For Existing HiveMatrix Installations

1. **Backup current installation:**
   ```bash
   cd /home/david/work
   tar -czf hivematrix-backup-$(date +%Y%m%d).tar.gz hivematrix-*
   ```

2. **Pull Helm changes:**
   ```bash
   cd hivematrix-helm
   git pull
   ```

3. **Update service registry:**
   ```bash
   python install_manager.py update-config
   ```

4. **Sync configurations:**
   ```bash
   python config_manager.py sync-all
   ```

5. **Restart services:**
   ```bash
   ./start.sh
   ```

## Future Enhancements

- [ ] Docker support for easier deployment
- [ ] Backup/restore functionality
- [ ] Health checks before app installation
- [ ] Rollback capability for failed updates
- [ ] Multi-environment support (dev/staging/prod)
- [ ] Automated testing before deployment
- [ ] App marketplace with ratings/reviews
- [ ] One-click app removal
- [ ] Dependency resolution (install required apps automatically)
- [ ] Configuration validation
- [ ] Secrets management (encrypt API keys)

## Support

For issues or questions:
- Check Helm logs: http://localhost:5004/logs
- View app status: http://localhost:5004/apps
- CLI status: `python cli.py status`
- GitHub Issues: https://github.com/ruapotato/hivematrix-helm/issues

## Credits

- HiveMatrix Architecture: David Thompson
- Helm Orchestrator: Refactored 2025-10-04
- Target Platform: Ubuntu 24.04 LTS
