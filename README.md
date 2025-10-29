# HiveMatrix Helm

**The Service Manager and Operations Center for HiveMatrix**

Helm is the operational control center for the HiveMatrix ecosystem. It manages the lifecycle of all services, collects centralized logs, monitors performance metrics, and provides security auditing tools. Helm provides both CLI tools and a comprehensive web dashboard for managing the entire platform.

---
## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
  - [Ubuntu Installation](#ubuntu-installation)
  - [Keycloak Setup](#keycloak-setup)
- [Starting HiveMatrix](#starting-hivematrix-ecosystem)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Command Line Interface](#command-line-interface-cli)
  - [Web Dashboard](#web-dashboard)
  - [API Endpoints](#api-endpoints)
- [Integrating Services](#integrating-services)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)
- [Database Schema](#database-schema)

---

## Overview

Helm provides:
- **Service Management**: Start, stop, restart, and monitor all HiveMatrix services
- **Centralized Logging**: Collect and query logs from all services via REST API
- **Performance Monitoring**: Track CPU, memory, and health metrics in real-time
- **Security Auditing**: Analyze port bindings and generate firewall configurations
- **User Management**: CRUD operations for Keycloak users and groups
- **Module Management**: Install, update, and remove HiveMatrix modules

**Port:** 5004 (standard)

### What Helm Does

Helm is the orchestration layer that ties the HiveMatrix ecosystem together:

1. **Controls Service Lifecycle** - Manages starting/stopping of Keycloak, Core, Nexus, Codex, Brainhair, Ledger, KnowledgeTree, and any custom modules
2. **Aggregates Logs** - All services send logs to Helm's PostgreSQL database for centralized viewing, filtering, and search
3. **Monitors Health** - Continuously checks service status, CPU/memory usage, and HTTP health endpoints
4. **Manages Users** - Provides UI and API for Keycloak user administration without direct Keycloak access
5. **Handles Security** - Audits network exposure and helps configure firewall rules
6. **Facilitates Deployment** - One-command startup script (`start.sh`) brings up the entire ecosystem

---

## Quick Start

Get the entire HiveMatrix ecosystem running in one command:

```bash
cd hivematrix-helm
./start.sh
```

**First run:** The script will:
- Install system dependencies (PostgreSQL, Java, etc.)
- Download and configure Keycloak
- Set up databases
- Create default admin user
- Start all services

**Access HiveMatrix:**
- Main URL: **https://localhost:443** (or https://YOUR_IP:443)
- Login: **admin / admin**

⚠️ **Change the default password after first login!**

### Auto-Start on Boot (Optional)

After initial setup, enable auto-start:

```bash
./install_autostart.sh
```

This creates a systemd user service that starts HiveMatrix on boot. See [AUTOSTART.md](AUTOSTART.md) for details.

---

## Features

### 🚀 Service Management
- Manages Keycloak, Core, Nexus, and all HiveMatrix services
- Start, stop, and restart services via CLI or web interface
- Development vs Production mode switching
- Process monitoring (PID, CPU, memory)
- Service discovery via `services.json`
- Multi-level health checks (process, port, HTTP)

### 📝 Centralized Logging
- Immutable log storage in PostgreSQL
- REST API for log ingestion from all services
- Context-aware logging with JSON support
- Trace ID for request correlation across services
- Advanced filtering and search (service, level, time range, trace ID, user)
- Real-time log streaming in web dashboard

### 📊 Performance Monitoring
- Real-time CPU and memory tracking
- Time-series metrics storage
- Historical performance data
- Service uptime tracking
- Auto-refresh dashboards

### 🔒 Security Auditing
- Network port binding analysis
- External exposure detection
- Firewall configuration generation (UFW/iptables)
- Security recommendations
- Admin user deletion protection

### 👥 User Management
- Keycloak user CRUD operations
- Group management (admin, technician, billing, client)
- Password reset functionality
- User synchronization between Keycloak and services

### 📦 Module Management
- Install HiveMatrix modules from Git repositories
- Update existing modules (git pull)
- Uninstall modules
- Installation log viewing

### 🖥️ Web Dashboard
- Service overview with live status
- Dashboard cards showing service health
- Centralized log viewer with filtering
- Metrics visualization
- Security audit reports
- User and module management interfaces

---

## Architecture

Helm integrates with HiveMatrix as the operations hub:

```
┌─────────────────────────────────────────┐
│  Core | Codex | Ledger | KnowledgeTree │
│       All HiveMatrix Services           │
└─────────────────────────────────────────┘
          ↓                  ↑
    Controls & Monitors   Sends Logs
          ↓                  ↑
┌─────────────────────────────────────────┐
│         HiveMatrix Helm (Port 5004)     │
│  ┌─────────────┐    ┌─────────────┐    │
│  │  Service    │    │  Logging    │    │
│  │  Manager    │    │  System     │    │
│  └─────────────┘    └─────────────┘    │
│         PostgreSQL Database             │
└─────────────────────────────────────────┘
```

**Key Components:**
- **Service Manager** (`service_manager.py`) - Controls service lifecycle, monitors processes
- **Log Aggregator** (REST API) - Collects logs from all services via `/api/logs/ingest`
- **Health Monitor** - Tracks service status (running/stopped), health checks, resource usage
- **Metrics Collector** - Gathers CPU/memory performance data
- **Security Auditor** - Analyzes network bindings and firewall status
- **PostgreSQL Database** - Stores logs, metrics, and service status

**Integration:**
- All services send logs to Helm via REST API
- Helm can start/stop services via process management
- Services remain independently runnable
- Helm provides centralized visibility and control
- Service configuration synced via `master_services.json`

---

## Installation

### Prerequisites

Before installing Helm, ensure you have:

- **Ubuntu 20.04+** (or compatible Linux distribution)
- **Python 3.8+**
- **PostgreSQL 12+**
- **Git**
- **wget** or **curl** (for downloading Keycloak)
- **Java 17+** (for Keycloak)

### Ubuntu Installation

#### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3 python3-venv python3-pip git wget openjdk-17-jre-headless
```

#### 2. Start PostgreSQL

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 3. Create Database and User

```bash
sudo -u postgres psql
```

In PostgreSQL, run these commands **one at a time**:

```sql
-- Create the database
CREATE DATABASE helm_db;

-- Create the user
CREATE USER helm_user WITH PASSWORD 'your_secure_password';

-- Grant database privileges
GRANT ALL PRIVILEGES ON DATABASE helm_db TO helm_user;

-- Connect to the helm_db database
\c helm_db

-- Grant schema permissions (required for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO helm_user;

-- Grant permissions on all current and future tables/sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO helm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO helm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO helm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO helm_user;

-- Exit PostgreSQL
\q
```

**Verify the setup:**
```bash
# Test you can connect
psql -h localhost -U helm_user -d helm_db
# Enter password when prompted
# If successful, you'll see the helm_db prompt
# Type \q to exit
```

#### 4. Install Python Dependencies

```bash
sudo apt install -y python3 python3-pip python3-venv libpq-dev python3-dev build-essential
```

#### 5. Set Up Helm

```bash
cd hivematrix-helm
python3 -m venv pyenv
source pyenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 6. Initialize Database

```bash
python init_db.py
```

When prompted, enter:
- **Host:** `localhost` (press Enter)
- **Port:** `5432` (press Enter)
- **Database Name:** `helm_db` (press Enter)
- **User:** `helm_user` (press Enter)
- **Password:** (your password from step 3)

The script will:
1. Test the database connection
2. Save configuration to `instance/helm.conf`
3. Create all required tables (log_entries, service_status, service_metrics)

#### 7. Configure Services

Edit `services.json` and `master_services.json`:

**services.json** - Used by Helm to manage services:
```json
{
  "keycloak": {
    "url": "http://localhost:8080",
    "path": "../keycloak-26.4.0",
    "port": 8080,
    "start_command": "bin/kc.sh start-dev",
    "type": "keycloak",
    "visible": true,
    "admin_only": true
  },
  "core": {
    "url": "http://localhost:5000",
    "path": "../hivematrix-core",
    "port": 5000,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true,
    "admin_only": true
  },
  "codex": {
    "url": "http://localhost:5010",
    "path": "../hivematrix-codex",
    "port": 5010,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true
  }
}
```

**master_services.json** - Synced to all services for service discovery:
```json
{
  "keycloak": {
    "url": "http://localhost:8080",
    "port": 8080
  },
  "core": {
    "url": "http://localhost:5000",
    "port": 5000
  },
  "codex": {
    "url": "http://localhost:5010",
    "port": 5010
  }
}
```

#### 8. Setup Keycloak (Automated)

Run the automated Keycloak setup:

```bash
./setup_keycloak.sh
```

This will:
- Download Keycloak 26.4.0
- Extract it to the parent directory (alongside hivematrix-helm)
- Update Helm's configuration
- Start Keycloak with admin credentials (admin/admin)

Then configure Keycloak for HiveMatrix:

```bash
./configure_keycloak.sh
```

This will automatically:
- Create the `hivematrix` realm
- Create the `core-client` with proper settings
- Retrieve and save the client secret to Core's `.flaskenv`
- Create the `admins` group
- Configure the group mapper
- Create an admin user (admin/admin)

#### 9. Start Everything

```bash
./start.sh
```

This will automatically:
- Start Keycloak, Core, Nexus
- Start additional services (Codex, Ledger, KnowledgeTree, Brainhair)
- Sync service configurations
- Start Helm web interface

Press `Ctrl+C` to cleanly stop all services.

#### 10. Verify Installation

```bash
curl http://localhost:5004/health
```

Should return:
```json
{"status": "healthy", "service": "helm", "timestamp": "..."}
```

#### 11. Access the Dashboard

Open your browser to `https://localhost:443/`

Login with:
- Username: **admin**
- Password: **admin**

You'll be redirected through Keycloak authentication and land on the Helm dashboard where you can manage all services.

---

## Starting HiveMatrix Ecosystem

HiveMatrix Helm manages all services including Keycloak.

### Quick Start (Recommended)

Use the unified startup script:

```bash
cd hivematrix-helm
./start.sh
```

This script will:
1. Start Keycloak (or detect if already running)
2. Start Core (or detect if already running)
3. Start Nexus (or detect if already running)
4. Start additional services (Codex, Ledger, KnowledgeTree, Brainhair)
5. Sync master services configuration to all services
6. Start Helm web interface
7. Display the Nexus URL for login

When complete, visit **https://localhost:443** to log in via Nexus/Keycloak.

**To stop all services:** Press `Ctrl+C` in the terminal running start.sh

The script will cleanly shut down all services in the correct order (Helm → services → Nexus → Core → Keycloak).

**Alternative:** If you need to stop services from a different terminal:

```bash
./stop_all.sh
```

### Manual Startup

If you prefer to start services individually:

#### Step 1: Start Required Services via CLI

Helm's web interface requires Keycloak, Core, and Nexus to be running. Use the CLI to start them:

```bash
cd hivematrix-helm

# Start Keycloak (shared authentication service)
python cli.py start keycloak

# Start Core (identity and access management)
python cli.py start core

# Start Nexus (frontend gateway)
python cli.py start nexus

# Check status
python cli.py status
```

#### Step 2: Start Helm Web Interface

Once the required services are running:

```bash
# Start Helm only (without starting other services)
python run.py
```

Helm will verify that Keycloak, Core, and Nexus are running. If any are missing, it will exit with instructions on how to start them.

#### Step 3: Access the Dashboard

Open your browser to `https://localhost:443` (Nexus login page)

After authentication via Keycloak, you can access:
- Helm Dashboard
- Start other services (Codex, Ledger, KnowledgeTree, etc.)
- Monitor all services
- View centralized logs
- Check metrics

---

## Configuration

### Environment Variables

File: `.flaskenv`

```bash
FLASK_APP=run.py
FLASK_ENV=development
CORE_SERVICE_URL='http://localhost:5000'
SERVICE_NAME='helm'
```

### Database Configuration

File: `instance/helm.conf` (created by `init_db.py`)

```ini
[database]
connection_string = postgresql://helm_user:password@localhost:5432/helm_db

[database_credentials]
db_host = localhost
db_port = 5432
db_user = helm_user
db_dbname = helm_db
```

### Service Registry

Helm maintains two service configuration files:

#### 1. `services.json` - Helm's Service Management Config

Used by Helm to manage and start services:

```json
{
  "service_name": {
    "url": "http://localhost:port",
    "path": "../relative/path/to/service",
    "port": port_number,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true,
    "admin_only": false
  }
}
```

**Fields:**
- `url` - HTTP endpoint for the service
- `path` - Relative path from helm directory to service directory
- `port` - Port the service runs on
- `type` - Service type: `python` (default) or `keycloak`
- `python_bin` - Path to Python executable (for Python services, relative to service directory)
- `run_script` - Script to run to start the service (for Python services)
- `start_command` - Command to start the service (for Keycloak and other non-Python services)
- `visible` - Whether service appears in Nexus sidebar (true/false)
- `admin_only` - Whether service is restricted to admins (true/false)

#### 2. `master_services.json` - Ecosystem-wide Service Directory

The master service directory that gets synced to all services when they start:

```json
{
  "service_name": {
    "url": "http://localhost:port",
    "port": port_number
  }
}
```

When a service starts, Helm automatically:
1. Reads `master_services.json`
2. Creates a simplified `services.json` in the service's directory
3. Ensures all services have a consistent view of the ecosystem

This eliminates manual configuration sync and ensures services can always discover each other.

---

## Usage

### Command Line Interface (CLI)

The Helm CLI allows you to manage services without the web interface:

```bash
# Show status of all services
python cli.py status

# List all configured services
python cli.py list

# Start a service
python cli.py start keycloak
python cli.py start core
python cli.py start codex --mode production

# Stop a service
python cli.py stop nexus

# Restart a service
python cli.py restart core --mode development
```

**Available Commands:**
- `status` - Show status of all services
- `list` - List all configured services
- `start <service>` - Start a service (optionally specify --mode)
- `stop <service>` - Stop a service
- `restart <service>` - Restart a service (optionally specify --mode)

**CLI is required** to start the initial services (Keycloak, Core, Nexus) before the web interface can be accessed.

### Web Dashboard

Access at `https://localhost:443/helm/` (requires Keycloak, Core, and Nexus to be running)

**Features:**
- **Service Overview** - Dashboard cards showing status of all services
- **Live Logs** - View logs from all services with real-time streaming
- **Metrics** - CPU, memory, uptime, and performance data
- **Service Details** - Detailed view per service with process logs
- **Security Audit** - Port binding analysis and firewall configuration
- **Module Management** - Install/update/remove HiveMatrix modules
- **User Management** - Manage Keycloak users and permissions

#### Dashboard Pages

All dashboard pages follow a consistent design system using Nexus's global CSS:

1. **Index (/)** - Main dashboard with service overview
   - Real-time status updates (5-second polling)
   - Service health indicators (healthy, degraded, unreachable)
   - Dashboard cards for each service with status badges
   - Settings section with Security Audit, Logs, Metrics, Modules, Users

2. **Logs (/logs)** - Centralized log viewer
   - Live log streaming with auto-scroll
   - Service and level filtering
   - Search functionality
   - Color-coded log levels
   - Pause/resume live updates

3. **Metrics (/metrics)** - Performance metrics
   - Service resource usage table
   - CPU and memory tracking
   - Uptime tracking
   - Auto-refresh every 5 seconds

4. **Security (/security)** - Security audit tool
   - Port binding analysis
   - External exposure detection
   - Firewall status check
   - Security recommendations
   - Firewall script generation (UFW/iptables)

5. **Modules (/modules)** - Module management (admin only)
   - Available and installed modules
   - Installation from Git repositories
   - Update (git pull) and uninstall actions
   - Installation logs modal

6. **Users (/users)** - User management (admin only)
   - Keycloak user CRUD operations
   - Group management (admin, technician, billing, client)
   - Password reset functionality
   - Admin user deletion protection

7. **Service Detail (/service/{name})** - Individual service view
   - Detailed service information
   - Status, health, PID, port, CPU, memory
   - Recent application logs (last 50)
   - Link to view process logs

8. **Service Logs (/service/{name}/logs)** - Process output viewer
   - View stdout/stderr from service processes
   - Real-time process logs
   - Filter by output type (both, stdout, stderr)
   - Shows actual console output from service startup

9. **Apps (/apps)** - Application management (if configured)
   - System dependencies
   - Installed applications with git status
   - Available applications (core and default)
   - Install from Git functionality

#### UI Design System

All Helm templates use:
- **Lucide Icons** - Modern, consistent iconography via CDN
- **BEM CSS Classes** - From Nexus's global.css (no local stylesheets)
- **Dark Mode Support** - Automatic theme switching via user preference
- **Responsive Layout** - Card-based design with proper spacing
- **Consistent Buttons** - Primary, secondary, danger, warning, success variants
- **Status Indicators** - Color-coded text (not badges) for better accessibility
- **Modal Dialogs** - For installation logs, user editing, password reset
- **Dashboard Cards** - Flexible card components with icons, titles, metadata

### API Endpoints

#### Service Control (Admin Only)

```bash
# List all services
GET /api/services

# Get all service statuses
GET /api/services/status

# Get specific service status
GET /api/services/{service_name}/status

# Get dashboard status (used by frontend)
GET /api/dashboard/status
```

**Note:** Service start/stop/restart functionality has been removed from the API. Services should be managed via the CLI or start.sh script.

#### Log Ingestion

```bash
# Ingest logs from services
POST /api/logs/ingest
{
  "service_name": "codex",
  "logs": [
    {
      "level": "INFO",
      "message": "Service started",
      "context": {"version": "1.0"},
      "trace_id": "abc-123",
      "user_id": "user@example.com"
    }
  ]
}

# Retrieve logs
GET /api/logs?service=codex&level=ERROR&limit=100

# Get specific log entry
GET /api/logs/{log_id}
```

**Query Parameters for /api/logs:**
- `service` - Filter by service name
- `level` - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `start_time` - ISO format datetime
- `end_time` - ISO format datetime
- `limit` - Number of records (default 100, max 1000)
- `offset` - Pagination offset
- `trace_id` - Filter by trace ID

#### Metrics

```bash
# Get service metrics
GET /api/metrics/{service_name}?start_time=2025-01-01T00:00:00&end_time=2025-01-02T00:00:00
```

#### Security

```bash
# Run security audit
GET /api/security/audit

# Apply firewall rules
POST /api/security/apply-firewall
```

#### User Management

```bash
# List Keycloak users
GET /api/users

# Create user
POST /api/users

# Get user details
GET /api/users/{user_id}

# Update user
PUT /api/users/{user_id}

# Delete user (admin protection enforced)
DELETE /api/users/{user_id}
```

#### Health Check

```bash
GET /health
```

---

## Integrating Services

To enable centralized logging in other HiveMatrix services:

### Option 1: Using HelmLogger Class

Copy `helm_logger.py` to your service:

```bash
cp hivematrix-helm/helm_logger.py your-service/
```

Use in your application:

```python
from helm_logger import HelmLogger

# Initialize logger
logger = HelmLogger('codex', 'http://localhost:5004')

# Log messages
logger.info('Service started', context={'version': '1.0'})
logger.error('Database connection failed',
             trace_id='abc-123',
             user_id='admin@example.com')
logger.warning('Rate limit approaching',
               context={'current': 90, 'max': 100})

# Ensure logs are sent
logger.flush()
```

### Option 2: Flask Integration

```python
from helm_logger import HelmLogHandler

# Add to your Flask app
helm_handler = HelmLogHandler('codex', 'http://localhost:5004')
app.logger.addHandler(helm_handler)
app.logger.setLevel(logging.INFO)

# Now all Flask logs go to Helm
app.logger.info('This goes to Helm!')
```

### Option 3: Direct API Calls

```python
import requests

def send_log(level, message, **kwargs):
    requests.post('http://localhost:5004/api/logs/ingest', json={
        'service_name': 'codex',
        'logs': [{
            'level': level,
            'message': message,
            **kwargs
        }]
    })

send_log('INFO', 'Service started')
```

---

## Production Deployment

### Running as Systemd Service

Create `/etc/systemd/system/helm.service`:

```ini
[Unit]
Description=HiveMatrix Helm Service
After=network.target postgresql.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/hivematrix-helm
Environment="PATH=/path/to/hivematrix-helm/pyenv/bin"
ExecStart=/path/to/hivematrix-helm/pyenv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable helm
sudo systemctl start helm
sudo systemctl status helm
```

### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/helm`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/helm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### SSL/TLS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Database Backups

Create backup script:

```bash
#!/bin/bash
BACKUP_DIR="/backups/helm"
mkdir -p $BACKUP_DIR
pg_dump -h localhost -U helm_user helm_db > $BACKUP_DIR/helm_$(date +%Y%m%d).sql
```

Add to crontab (daily at 3 AM):

```bash
crontab -e
# Add:
0 3 * * * /path/to/backup-script.sh
```

### Log Retention

Create cleanup script or add to crontab (delete logs older than 90 days, runs daily at 2 AM):

```bash
crontab -e
# Add:
0 2 * * * cd /path/to/hivematrix-helm && pyenv/bin/python -c "from app import app; from extensions import db; from models import LogEntry; from datetime import datetime, timedelta; app.app_context().push(); cutoff = datetime.utcnow() - timedelta(days=90); LogEntry.query.filter(LogEntry.timestamp < cutoff).delete(); db.session.commit()"
```

### PostgreSQL Performance Tuning

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 16MB
min_wal_size = 1GB
max_wal_size = 4GB
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

---

## Troubleshooting

### Keycloak Issues

**Can't login to Keycloak admin console**
- Delete data directory in the Keycloak installation (e.g., `rm -rf ../keycloak-26.4.0/data`)
- Restart Keycloak: `python cli.py restart keycloak`
- Wait 20 seconds for initialization
- Login with admin/admin

**Keycloak won't start**
- Check Java is installed: `java -version`
- Install Java 17: `sudo apt install -y openjdk-17-jre-headless`
- Check port 8080 isn't in use: `sudo lsof -i :8080`

**"Invalid username or password" when logging into HiveMatrix**
- Run: `./configure_keycloak.sh` to set up the hivematrix realm
- Make sure you're using credentials for the hivematrix realm, not master
- Default: admin/admin

### Helm Won't Start

**Error: "Database not configured"**
- Run: `python init_db.py`
- Check that `instance/helm.conf` exists

**Error: "Required services not running"**
- Keycloak, Core, and Nexus must be running before Helm starts
- Start them: `python cli.py start keycloak && python cli.py start core && python cli.py start nexus`

**Error: Connection refused to PostgreSQL**
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Start it: `sudo systemctl start postgresql`
- Test connection: `psql -h localhost -U helm_user -d helm_db`

**Error: Permission denied**
- Check file ownership: `ls -la`
- Fix with: `sudo chown -R $USER:$USER /path/to/hivematrix-helm`
- Make start script executable: `chmod +x start.sh`

### Service Won't Start via Helm

**Check:**
1. Service path in `services.json` is correct
2. Python virtualenv exists at specified path
3. Service's `run.py` exists
4. Port not already in use: `sudo lsof -i :5001`

**View Helm logs for details:**
- Web dashboard: https://localhost:443/helm/logs
- Or check terminal output

### Logs Not Appearing

**Check:**
1. Service is sending to correct Helm URL
2. Network connectivity: `curl http://localhost:5004/health`
3. Database tables exist: `psql -h localhost -U helm_user -d helm_db -c "\dt"`
4. PostgreSQL is running: `sudo systemctl status postgresql`

**Test log ingestion:**
```bash
curl -X POST http://localhost:5004/api/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "test",
    "logs": [{
      "level": "INFO",
      "message": "Test log"
    }]
  }'
```

### Service Shows Running but Unhealthy

1. Service may be starting up (wait 10 seconds)
2. Check service logs directly
3. Service may not implement `/health` endpoint
4. Firewall may be blocking the port
5. SSL certificate issues (for HTTPS services like Nexus)

### Port Already in Use

```bash
# Find what's using port 5004
sudo lsof -i :5004

# Kill the process
sudo kill -9 <PID>
```

### PostgreSQL Connection Issues

**Test connection:**
```bash
psql -h localhost -U helm_user -d helm_db
```

**Check user exists:**
```bash
sudo -u postgres psql -c "\du" | grep helm_user
```

**Check database exists:**
```bash
sudo -u postgres psql -l | grep helm_db
```

**Reset password:**
```sql
sudo -u postgres psql
ALTER USER helm_user WITH PASSWORD 'new_password';
\q
# Then re-run: python init_db.py
```

---

## Database Schema

Helm uses **PostgreSQL** for production-grade performance and reliability.

### Tables

#### log_entries
**Purpose:** Immutable log storage from all services

**Columns:**
- `id` (BigInteger, Primary Key) - Auto-incrementing log ID
- `timestamp` (DateTime, Indexed) - When log was created
- `service_name` (String, Indexed) - Source service
- `level` (String, Indexed) - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `message` (Text) - Log message
- `context` (JSONB) - Additional context data
- `trace_id` (String, Indexed) - Request/operation trace ID
- `user_id` (String, Indexed) - User who triggered the log
- `hostname` (String) - Server hostname
- `process_id` (Integer) - Process ID

**Features:**
- Logs cannot be modified or deleted (immutable)
- Indexed for fast queries by timestamp, service, level, trace_id, user_id
- Supports millions of log entries efficiently
- JSONB context field for structured data

#### service_status
**Purpose:** Current status and health of each service

**Columns:**
- `id` (Integer, Primary Key)
- `service_name` (String, Unique) - Service identifier
- `status` (String) - running, stopped, error, unknown
- `pid` (Integer) - Process ID
- `port` (Integer) - Port number
- `started_at` (DateTime) - When service was started
- `last_checked` (DateTime) - Last health check time
- `health_status` (String) - healthy, unhealthy, degraded
- `health_message` (Text) - Health check details
- `cpu_percent` (Float) - CPU usage percentage
- `memory_mb` (Float) - Memory usage in MB

**Features:**
- One record per service
- Updated in real-time by monitoring system
- Tracks resource usage and health

#### service_metrics
**Purpose:** Time-series performance data

**Columns:**
- `id` (BigInteger, Primary Key)
- `service_name` (String, Indexed) - Service identifier
- `timestamp` (DateTime, Indexed) - Metric timestamp
- `metric_name` (String) - Name of metric (e.g., cpu_percent, memory_mb)
- `metric_value` (Float) - Metric value
- `tags` (JSONB) - Additional metric tags

**Features:**
- Used for historical analysis and trending
- Indexed for efficient time-range queries
- Supports custom application metrics

### Indexes

```sql
-- Log queries optimization
CREATE INDEX idx_logs_timestamp ON log_entries(timestamp DESC);
CREATE INDEX idx_logs_service ON log_entries(service_name, timestamp DESC);
CREATE INDEX idx_logs_level ON log_entries(level, timestamp DESC);
CREATE INDEX idx_logs_trace ON log_entries(trace_id);
CREATE INDEX idx_logs_user ON log_entries(user_id);

-- Metric queries optimization
CREATE INDEX idx_metrics_service_time ON service_metrics(service_name, timestamp DESC);
CREATE INDEX idx_metrics_name ON service_metrics(metric_name, timestamp DESC);
```

---

## Security

**Authentication:**
- All admin actions require admin JWT token from Core
- Log ingestion accepts service tokens or user tokens
- Read operations require authentication
- Helm validates tokens via Core's public key

**Authorization:**
- **Admin:** Full control (manage services, all logs, user management)
- **Technician:** Read logs, view metrics
- **Billing:** Service-specific logs only
- **Client:** Limited access

**Best Practices:**
1. Change default Keycloak admin password (admin/admin) immediately
2. Use strong PostgreSQL passwords
3. Enable firewall (ufw) and only allow required ports
4. Use HTTPS in production (via Nexus with SSL)
5. Run as non-root user
6. Keep system updated
7. Restrict database access to localhost unless needed
8. Back up database regularly
9. Configure log retention to manage storage
10. Admin user cannot be deleted (enforced protection)

---

## Related Modules

- **HiveMatrix Core** (Port 5000): Authentication and identity management
- **HiveMatrix Nexus** (Port 443): UI composition and routing proxy with SSL
- **HiveMatrix Codex** (Port 5010): Data platform for companies, contacts, assets, tickets
- **HiveMatrix Brainhair** (Port 5050): AI assistant with access to organizational data
- **HiveMatrix Ledger** (Port 5030): Billing calculations and client invoicing
- **HiveMatrix KnowledgeTree** (Port 5020): Documentation and knowledge base

---

## License

See main HiveMatrix LICENSE file

---

## Contributing

When adding features to Helm:
1. Follow the HiveMatrix architecture patterns
2. Use `@token_required` for all protected routes
3. Use BEM classes for all HTML (no CSS in this service)
4. Update this README with new API endpoints
5. Test service management and logging thoroughly
6. Consider impact on all services in the ecosystem

For questions, refer to `ARCHITECTURE.md` in the main HiveMatrix repository.
