# HiveMatrix Helm

**Service Orchestration, Monitoring, and Centralized Logging for HiveMatrix**

Helm is the operational control center for the HiveMatrix ecosystem. It provides service management, real-time monitoring, centralized logging, and performance metrics collection for all HiveMatrix services.

---
## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
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
- Requires Keycloak, Core, and Nexus to be running for web access

### 📝 Centralized Logging
- Immutable log storage in PostgreSQL
- REST API for log ingestion from all services
- Context-aware logging with JSON support
- Trace ID for request correlation
- Advanced filtering and search

### 📊 Performance Monitoring
- Real-time CPU and memory tracking
- Time-series metrics storage
- Multi-level health checks (process, port, HTTP)
- Historical performance data

### 🖥️ Web Dashboard
- Service overview with live status
- One-click service control (admin only)
- Centralized log viewer
- Metrics visualization

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
- **Service Manager** - Controls service lifecycle
- **Log Aggregator** - Collects logs from all services
- **Health Monitor** - Tracks service status
- **Metrics Collector** - Gathers performance data
- **PostgreSQL Database** - Stores logs, metrics, and service status

**Integration:**
- All services send logs to Helm via REST API
- Helm can start/stop services via process management
- Services remain independently runnable
- Helm provides centralized visibility

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
3. Create all required tables

#### 7. Configure Services

Edit `services.json`:

```json
{
  "core": {
    "url": "http://localhost:5000",
    "path": "../hivematrix-core",
    "port": 5000,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py"
  },
  "codex": {
    "url": "http://localhost:5001",
    "path": "../hivematrix-codex",
    "port": 5001,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py"
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

**Alternative: Manual Setup**

If you prefer manual setup or already have Keycloak, edit `services.json` to include Keycloak:

```json
{
  "keycloak": {
    "url": "http://localhost:8080",
    "path": "../keycloak-26.3.5",
    "port": 8080,
    "start_command": "bin/kc.sh start-dev",
    "type": "keycloak"
  },
  "core": {
    "url": "http://localhost:5000",
    "path": "../hivematrix-core",
    "port": 5000,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py"
  },
  ...other services...
}
```

#### 9. Start Everything

```bash
./start.sh
```

This will automatically:
- Start Keycloak, Core, Nexus
- Start additional services (Codex, Ledger, KnowledgeTree)
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

Open your browser to `http://localhost:8000/`

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
4. Start additional services (Codex, Ledger, KnowledgeTree)
5. Sync master services configuration to all services
6. Start Helm web interface
7. Display the Nexus URL for login

When complete, visit **http://localhost:8000** to log in via Nexus/Keycloak.

**To stop all services:** Press `Ctrl+C` in the terminal running start.sh

The script will cleanly shut down all services in the correct order (Helm → Nexus → Core → Keycloak).

**Alternative:** If you need to stop services from a different terminal (or if the startup terminal was closed):

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

Open your browser to `http://localhost:8000` (Nexus login page)

After authentication via Keycloak, you can access:
- Helm Dashboard at `http://localhost:5004`
- Start other services (Codex, Ledger, KnowledgeTree, etc.)
- Monitor all services
- View centralized logs
- Check metrics

### Alternative: Manual Service Startup

You can start services manually instead of using Helm:

```bash
# Start Keycloak manually
cd ../keycloak-26.4.0
export KEYCLOAK_ADMIN=admin
export KEYCLOAK_ADMIN_PASSWORD=admin
bin/kc.sh start-dev

# Start other services in separate terminals
cd ../hivematrix-core && ./start.sh
cd ../hivematrix-nexus && ./start.sh
cd ../hivematrix-helm && python run.py
```

---

### General Installation

For non-Ubuntu systems, follow these steps:

1. **Install PostgreSQL** for your platform
2. **Create database and user** (see Ubuntu steps 3 above)
3. **Install Python 3.8+** and pip
4. **Install build dependencies** for psycopg2
5. **Follow steps 5-9** from Ubuntu installation

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
    "run_script": "run.py"
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

#### 2. `master_services.json` - Ecosystem-wide Service Directory

The master service directory that gets synced to all services when they start:

```json
{
  "service_name": {
    "url": "http://localhost:port",
    "port": port_number,
    "description": "Service description"
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

Access at `http://localhost:5004/` (requires Keycloak, Core, and Nexus to be running)

**Features:**
- **Service Overview** - View status of all services
- **Service Control** - Start/stop/restart services (admin only)
- **Live Logs** - View logs from all services with real-time streaming
- **Metrics** - CPU, memory, uptime, and performance data
- **Service Details** - Detailed view per service with process logs
- **Security Audit** - Port binding analysis and firewall configuration
- **Module Management** - Install/update/remove HiveMatrix modules
- **User Management** - Manage Keycloak users and permissions

#### Dashboard Pages

All dashboard pages follow a consistent design system using Nexus's global CSS:

1. **Index (/)** - Main dashboard with service overview table
   - Real-time status updates (5-second polling)
   - Service health indicators
   - CPU/Memory usage
   - Log statistics (errors, warnings, info)
   - Quick action buttons (start/stop/restart) with icons

2. **Logs (/logs)** - Centralized log viewer
   - Live log streaming with auto-scroll
   - Service and level filtering
   - Search functionality
   - Color-coded log levels

3. **Metrics (/metrics)** - Performance metrics
   - Service resource usage table
   - Uptime tracking
   - Auto-refresh every 5 seconds

4. **Security (/security)** - Security audit tool
   - Port binding analysis
   - Firewall status check
   - Security recommendations
   - Firewall script generation (UFW/iptables)

5. **Modules (/modules)** - Module management (admin only)
   - Available and installed modules
   - Installation logs modal
   - Update and uninstall actions
   - Custom module installation from Git

6. **Users (/users)** - User management (admin only)
   - Keycloak user CRUD operations
   - Group management (admin, technician, billing, client)
   - Password reset functionality
   - Admin user deletion protection

7. **Service Detail (/service/{name})** - Individual service view
   - Detailed service information
   - Recent application logs
   - Service control buttons

8. **Service Logs (/service/{name}/logs)** - Process output viewer
   - View stdout/stderr from service processes
   - Real-time process logs
   - Filter by output type (both, stdout, stderr)

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
- **Tab Navigation** - For multi-section pages (apps, modules)

### API Endpoints

#### Service Control (Admin Only)

```bash
# List all services
GET /api/services

# Get all service statuses
GET /api/services/status

# Get specific service status
GET /api/services/{service_name}/status

# Start a service
POST /api/services/{service_name}/start
{
  "mode": "development"  # or "production"
}

# Stop a service
POST /api/services/{service_name}/stop

# Restart a service
POST /api/services/{service_name}/restart
{
  "mode": "development"
}
```

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
- Web dashboard: http://localhost:5004/logs
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
- **Admin:** Full control (start/stop services, all logs)
- **Technician:** Read logs, view metrics
- **Billing:** Service-specific logs only
- **Client:** Limited access

**Best Practices:**
1. Use strong PostgreSQL passwords
2. Enable firewall (ufw) and only allow required ports
3. Use HTTPS in production (Let's Encrypt)
4. Run as non-root user
5. Keep system updated
6. Restrict database access to localhost unless needed
7. Back up database regularly
8. Configure log retention to manage storage

---

## Future Enhancements

- WebSocket support for live log streaming
- Alert system for errors and downtime
- Automated service restart on failure
- Advanced metrics visualization with charts
- Container/Docker support
- Distributed tracing integration (OpenTelemetry)
- Multi-instance Helm deployment
- Elasticsearch integration for log search
- Time-series database (InfluxDB) for metrics
- Anomaly detection
- Predictive scaling

---

## License

See main HiveMatrix LICENSE file
