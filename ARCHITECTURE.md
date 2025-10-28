# HiveMatrix Architecture & AI Development Guide

**Version 4.0**

## 1. Core Philosophy & Goals

This document is the single source of truth for the HiveMatrix architecture. Its primary audience is the AI development assistant responsible for writing and maintaining the platform's code. Adherence to these principles is mandatory.

Our goals are, in order of priority:

1.  **AI Maintainability:** Each individual application (e.g., `Resolve`, `Codex`) must remain small, focused, and simple. We sacrifice some traditional development conveniences to achieve this.
2.  **Modularity:** The platform is a collection of independent, fully functional applications that can be composed together.
3.  **Simplicity & Explicitness:** We favor simple, explicit patterns over complex, "magical" ones. Assume code is correct and error out to expose flaws rather than building defensive checks.

## 2. The Monolithic Service Pattern

Each module in HiveMatrix (e.g., `Resolve`, `Architect`, `Codex`) is a **self-contained, monolithic application**. Each application is a single, deployable unit responsible for its own business logic, database, and UI rendering.

* **Server-Side Rendering:** Applications **must** render their user interfaces on the server side, returning complete HTML documents.
* **Data APIs:** Applications may *also* expose data-only APIs (e.g., `/api/tickets`) that return JSON.
* **Data Isolation:** Each service owns its own database. You are forbidden from accessing another service's database directly.

## 3. End-to-End Authentication Flow

The platform operates on a centralized login model orchestrated by `Core` and `Nexus`. No service handles user credentials directly. All authentication flows through Keycloak, and sessions are managed by Core with revocation support.

### Initial Login Flow

1.  **Initial Request:** A user navigates to `https://your-server/` (Nexus on port 443).
2.  **Auth Check:** `Nexus` checks the user's session. If no valid session token exists, it stores the target URL and redirects to the login endpoint.
3.  **Keycloak Proxy:** The user is redirected to `/keycloak/realms/hivematrix/protocol/openid-connect/auth`. Nexus proxies this to the local Keycloak server (port 8080) with proper X-Forwarded headers.
4.  **Keycloak Login:** User enters credentials on the Keycloak login page (proxied through Nexus).
5.  **OAuth Callback:** After successful login, Keycloak redirects to `https://your-server/keycloak-callback` with an authorization code.
6.  **Token Exchange:** `Nexus` receives the callback and:
    - Exchanges the authorization code for Keycloak access token (using backend localhost:8080 connection)
    - Calls `Core`'s `/api/token/exchange` endpoint with the Keycloak access token
7.  **Session Creation:** `Core` receives the Keycloak token and:
    - Validates it with Keycloak's userinfo endpoint
    - Extracts user info and group membership
    - Determines permission level from Keycloak groups
    - **Creates a server-side session** with a unique session ID
    - **Mints a HiveMatrix JWT** signed with Core's private RSA key containing:
      - User identity (sub, name, email, preferred_username)
      - Permission level (admin, technician, billing, or client)
      - Group membership
      - **jti (JWT ID)** - The session ID for revocation tracking
      - Standard JWT claims (iss, iat, exp)
      - 1-hour expiration (exp)
    - Stores session in memory with TTL (Time To Live)
8.  **JWT to Nexus:** `Core` returns the HiveMatrix JWT to `Nexus`.
9.  **Session Storage:** `Nexus` stores the JWT in the user's Flask session cookie.
10. **Final Redirect:** `Nexus` redirects the user to their originally requested URL.
11. **Authenticated Access:** For subsequent requests:
    - `Nexus` retrieves the JWT from the session
    - Validates the JWT signature using Core's public key
    - **Checks with Core** that the session (jti) hasn't been revoked
    - If valid, proxies the request to backend services with `Authorization: Bearer <token>` header
12. **Backend Verification:** Backend services verify the JWT using Core's public key at `/.well-known/jwks.json`.

### Permission Levels

HiveMatrix supports four permission levels, determined by Keycloak group membership:

- **admin**: Members of the `admins` group - full system access
- **technician**: Members of the `technicians` group - technical operations
- **billing**: Members of the `billing` group - financial operations
- **client**: Default level for users not in any special group - limited access

Services can access the user's permission level via `g.user.get('permission_level')` and enforce authorization using the `@admin_required` decorator or custom permission checks.

### Session Management & Logout Flow

HiveMatrix implements **revokable sessions** with automatic expiration to ensure proper security.

#### Session Lifecycle

**Session Creation:**
- When a user logs in, `Core` creates a server-side session with:
  - Unique session ID (stored as `jti` in the JWT)
  - User data (sub, name, email, permission_level, groups)
  - Creation timestamp (`created_at`)
  - Expiration timestamp (`expires_at`) - 1 hour from creation
  - Revocation flag (`revoked`) - initially false

**Session Validation:**
- On each request, `Nexus` calls `Core`'s `/api/token/validate` endpoint
- `Core` checks:
  1. JWT signature is valid
  2. JWT has not expired (exp claim)
  3. Session ID (jti) exists in the session store
  4. Session has not expired (expires_at)
  5. Session has not been revoked (revoked flag)
- If any check fails, the session is invalid and the user must re-authenticate

**Session Expiration:**
- Sessions automatically expire after 1 hour
- Expired sessions are removed from memory during cleanup
- Users must log in again after expiration

#### Logout Flow

1. **User Clicks Logout:** User navigates to `/logout` endpoint on Nexus
2. **Retrieve Token:** Nexus retrieves the JWT from the user's session
3. **Revoke at Core:** Nexus calls `Core`'s `/api/token/revoke` with the JWT:
   ```
   POST /api/token/revoke
   {
     "token": "<jwt_token>"
   }
   ```
4. **Mark as Revoked:** Core:
   - Decodes the JWT to extract session ID (jti)
   - Marks the session as revoked in the session store
   - Returns success response
5. **Clear Client State:** Nexus:
   - Clears the server-side Flask session
   - Returns HTML that clears browser storage and cookies
   - Redirects to home page
6. **Re-authentication Required:** Next request to any protected page:
   - Nexus has no session → redirects to login
   - OR if somehow a token is still cached → Core validation fails (session revoked)

#### Core Session Manager

The `SessionManager` class in `hivematrix-core/app/session_manager.py` provides:

```python
class SessionManager:
    def create_session(user_data) -> session_id
    def validate_session(session_id) -> user_data or None
    def revoke_session(session_id) -> bool
    def cleanup_expired() -> count
```

**Production Note:** The current implementation uses in-memory storage. For production deployments with multiple Core instances, sessions should be stored in Redis or a database for shared state.

### Core API Endpoints

**Token Exchange:**
```
POST /api/token/exchange
Body: { "access_token": "<keycloak_access_token>" }
Response: { "token": "<hivematrix_jwt>" }
```

**Token Validation:**
```
POST /api/token/validate
Body: { "token": "<hivematrix_jwt>" }
Response: { "valid": true, "user": {...} } or { "valid": false, "error": "..." }
```

**Token Revocation:**
```
POST /api/token/revoke
Body: { "token": "<hivematrix_jwt>" }
Response: { "message": "Session revoked successfully" }
```

**Public Key (JWKS):**
```
GET /.well-known/jwks.json
Response: { "keys": [{ "kty": "RSA", "kid": "...", ... }] }
```

## 4. Service-to-Service Communication

Services may need to call each other's APIs (e.g., Treasury calling Codex to get billing data). This is done using **service tokens** minted by Core.

### Service Token Flow

1. **Request Service Token:** The calling service (e.g., Treasury) makes a POST request to `Core`'s `/service-token` endpoint:
   ```json
   {
     "calling_service": "treasury",
     "target_service": "codex"
   }
   ```

2. **Core Mints Token:** Core creates a short-lived JWT (5 minutes) with:
   ```json
   {
     "iss": "hivematrix.core",
     "sub": "service:treasury",
     "calling_service": "treasury",
     "target_service": "codex",
     "type": "service",
     "iat": 1234567890,
     "exp": 1234568190
   }
   ```

3. **Make Authenticated Request:** The calling service uses this token in the Authorization header when calling the target service's API.

4. **Target Service Verification:** The target service verifies the token using Core's public key and checks the `type` field to determine if it's a service call.

### Service Client Helper

All services include a `service_client.py` helper that automates this flow:

```python
from app.service_client import call_service

# Make a service-to-service API call
response = call_service('codex', '/api/companies')
companies = response.json()
```

The `call_service` function:
- Automatically requests a service token from Core
- Adds the Authorization header
- Makes the HTTP request
- Returns the response

### Service Discovery

Services are registered in two configuration files:

**`master_services.json`** - Master service registry (simplified format):
```json
{
  "codex": {
    "url": "http://localhost:5010",
    "port": 5010
  },
  "archive": {
    "url": "http://localhost:5012",
    "port": 5012
  }
}
```

**`services.json`** - Full service configuration (extended format):
```json
{
  "codex": {
    "url": "http://localhost:5010",
    "path": "../hivematrix-codex",
    "port": 5010,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true
  },
  "archive": {
    "url": "http://localhost:5012",
    "path": "../hivematrix-archive",
    "port": 5012,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true
  }
}
```

**When adding a new service:**
1. Add entry to `master_services.json` (required for Nexus service discovery)
2. Add extended entry to `services.json` (required for Helm service management)
3. Both files must be updated for the service to be properly discovered and started

### Authentication Decorator Behavior

The `@token_required` decorator in each service handles both user and service tokens:

```python
@token_required
def api_endpoint():
    if g.is_service_call:
        # Service-to-service call
        calling_service = g.service
        # Service calls bypass user-level permission checks
    else:
        # User call
        user = g.user
        # Apply user permission checks as needed
```

Service calls automatically bypass user-level permission requirements, as they represent trusted inter-service communication.

## 5. Frontend: The Smart Proxy Composition Model

The user interface is a composition of the independent applications, assembled by the `Nexus` proxy.

### The Golden Rule of Styling

**Applications are forbidden from containing their own styling.** All visual presentation (CSS) is handled exclusively by `Nexus` injecting a global stylesheet. Applications must use the BEM classes defined in this document.

### The `Nexus` Service

`Nexus` acts as the central gateway. Its responsibilities are:
* Enforcing authentication for all routes.
* Proxying requests to the appropriate backend service based on the URL path.
* Injecting the global `global.css` stylesheet into any HTML responses.
* Discovering backend services via the `services.json` file.

**File: `hivematrix-nexus/services.json`**
```json
{
  "template": {
    "url": "http://localhost:5001"
  },
  "codex": {
    "url": "http://localhost:5010"
  }
}
```

### URL Prefix Handling with ProxyFix

When services are accessed through the Nexus proxy, they need to know their URL prefix to generate correct URLs. This is handled via X-Forwarded headers and werkzeug's `ProxyFix` middleware.

#### How Nexus Proxies Requests

1. User requests: `https://192.168.1.233/knowledgetree/browse/`
2. Nexus strips the service prefix before forwarding
3. Nexus adds X-Forwarded headers including `X-Forwarded-Prefix: /knowledgetree`
4. Backend service receives: `/browse/` with headers indicating the prefix
5. Backend's ProxyFix middleware sets SCRIPT_NAME from X-Forwarded-Prefix
6. Flask's `url_for()` generates correct URLs: `/knowledgetree/browse/`

#### Nexus Configuration

Nexus automatically adds X-Forwarded headers when proxying to backend services:

```python
# In hivematrix-nexus/app/routes.py
headers['Authorization'] = f"Bearer {token}"
headers['X-Forwarded-For'] = request.remote_addr
headers['X-Forwarded-Proto'] = 'https' if request.is_secure else 'http'
headers['X-Forwarded-Host'] = request.host
headers['X-Forwarded-Prefix'] = f'/{service_name}'  # e.g., /knowledgetree
```

#### Backend Service Configuration

Each service must use werkzeug's `ProxyFix` middleware to respect these headers:

```python
# In app/__init__.py
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # Trust X-Forwarded-For
    x_proto=1,    # Trust X-Forwarded-Proto (http/https)
    x_host=1,     # Trust X-Forwarded-Host
    x_prefix=1    # Trust X-Forwarded-Prefix (sets SCRIPT_NAME)
)
```

**Important**: Do NOT use custom PrefixMiddleware. Nexus already strips the prefix before forwarding, so the backend receives clean paths without the service name. The ProxyFix middleware only affects URL generation, not route matching.

#### Authentication for AJAX Requests

When making AJAX requests from frontend JavaScript, you must include `credentials: 'same-origin'` in fetch options:

```javascript
fetch('/api/search?query=test', {
    credentials: 'same-origin'
})
```

This ensures the access_token cookie is sent with the request. The `@token_required` decorator checks both:
1. `Authorization: Bearer <token>` header (from Nexus proxy)
2. `access_token` cookie (from browser, as fallback)

```python
# In app/auth.py - token_required decorator
auth_header = request.headers.get('Authorization')
token = None

if auth_header and auth_header.startswith('Bearer '):
    token = auth_header.split(' ')[1]
else:
    # Fall back to cookie
    token = request.cookies.get('access_token')
```

## 6. Configuration Management & Auto-Installation

HiveMatrix uses a centralized configuration system managed by `hivematrix-helm`. All service configurations are generated and synchronized from Helm's master configuration.

### Configuration Manager (`config_manager.py`)

The `ConfigManager` class in `hivematrix-helm/config_manager.py` is responsible for:

- **Master Configuration Storage**: Maintains `instance/configs/master_config.json` with system-wide settings
- **Per-App Configuration Generation**: Generates `.flaskenv` and `instance/[app].conf` files for each service
- **Centralized Settings**: Ensures consistent Keycloak URLs, hostnames, and service URLs across all apps

#### Master Configuration Structure

```json
{
  "system": {
    "hostname": "localhost",
    "environment": "development",
    "secret_key": "<generated>",
    "log_level": "INFO"
  },
  "keycloak": {
    "url": "http://localhost:8080",
    "realm": "hivematrix",
    "client_id": "core-client",
    "client_secret": "<generated>",
    "admin_username": "admin",
    "admin_password": "admin"
  },
  "databases": {
    "postgresql": {
      "host": "localhost",
      "port": 5432,
      "admin_user": "postgres"
    },
    "neo4j": {
      "uri": "bolt://localhost:7687",
      "user": "neo4j",
      "password": "password"
    }
  },
  "apps": {
    "template": {
      "port": 5040,
      "database": "postgresql",
      "db_name": "template_db",
      "db_user": "template_user"
    }
  }
}
```

#### .flaskenv Generation

The `generate_app_dotenv(app_name)` method creates `.flaskenv` files with:

- **Flask Configuration**: `FLASK_APP`, `FLASK_ENV`, `SECRET_KEY`, `SERVICE_NAME`
- **Keycloak Configuration**: Automatically adjusts URLs based on hostname (localhost vs production)
  - For `core`: Direct Keycloak connection (`http://localhost:8080/realms/hivematrix`)
  - For other services: Proxied URL (`https://hostname/keycloak` or `http://localhost:8080`)
- **Service URLs**: `CORE_SERVICE_URL`, `NEXUS_SERVICE_URL`
- **Database Configuration**: `DB_HOST`, `DB_PORT`, `DB_NAME` (if database is configured)
- **JWT Configuration**: For Core service only - `JWT_PRIVATE_KEY_FILE`, `JWT_PUBLIC_KEY_FILE`, etc.

Example generated `.flaskenv`:
```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=abc123...
SERVICE_NAME=template

# Keycloak Configuration
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_BACKEND_URL=http://localhost:8080
KEYCLOAK_REALM=hivematrix
KEYCLOAK_CLIENT_ID=core-client

# Service URLs
CORE_SERVICE_URL=http://localhost:5000
NEXUS_SERVICE_URL=http://localhost:8000
```

#### instance/app.conf Generation

The `generate_app_conf(app_name)` method creates ConfigParser-formatted files with:

- **Database Section**: PostgreSQL connection string with credentials
- **App-Specific Sections**: Custom configuration sections defined in master config

Example generated `instance/template.conf`:
```ini
[database]
connection_string = postgresql://template_user:password@localhost:5432/template_db
db_host = localhost
db_port = 5432
db_name = template_db
db_user = template_user
```

#### Configuration Sync

To update all installed apps with current configuration:
```bash
cd hivematrix-helm
source pyenv/bin/activate
python config_manager.py sync-all
```

This is automatically called by `start.sh` on each startup to ensure configurations are current.

### Auto-Installation Architecture

HiveMatrix uses a registry-based installation system that allows services to be installed through the Helm web interface.

#### App Registry (`apps_registry.json`)

All installable apps are defined in `hivematrix-helm/apps_registry.json`. This file is the authoritative source for all HiveMatrix services and is used by `install_manager.py` to automatically generate both `services.json` and `master_services.json`.

```json
{
  "core_apps": {
    "core": {
      "name": "HiveMatrix Core",
      "description": "Authentication & service registry - Required",
      "git_url": "https://github.com/ruapotato/hivematrix-core",
      "port": 5000,
      "required": true,
      "dependencies": ["postgresql"],
      "install_order": 1
    },
    "nexus": {
      "name": "HiveMatrix Nexus",
      "description": "Frontend gateway and UI - Required",
      "git_url": "https://github.com/ruapotato/hivematrix-nexus",
      "port": 443,
      "required": true,
      "dependencies": ["core", "keycloak"],
      "install_order": 2
    }
  },
  "default_apps": {
    "codex": {
      "name": "HiveMatrix Codex",
      "description": "Central data hub for MSP operations",
      "git_url": "https://github.com/ruapotato/hivematrix-codex",
      "port": 5010,
      "required": false,
      "dependencies": ["postgresql", "core"],
      "install_order": 3
    },
    "archive": {
      "name": "HiveMatrix Archive",
      "description": "Document and file archival system",
      "git_url": "https://github.com/ruapotato/hivematrix-archive",
      "port": 5012,
      "required": false,
      "dependencies": ["core", "codex"],
      "install_order": 8
    },
    "template": {
      "name": "HiveMatrix Template",
      "description": "Template for new HiveMatrix services",
      "git_url": "https://github.com/ruapotato/hivematrix-template",
      "port": 5040,
      "required": false,
      "dependencies": ["core"],
      "install_order": 6
    }
  },
  "system_dependencies": {
    "keycloak": {
      "name": "Keycloak",
      "description": "Authentication server",
      "version": "26.4.0",
      "download_url": "https://github.com/keycloak/keycloak/releases/download/26.4.0/keycloak-26.4.0.tar.gz",
      "port": 8080,
      "required": true,
      "install_order": 0
    },
    "postgresql": {
      "name": "PostgreSQL",
      "description": "Relational database",
      "apt_package": "postgresql postgresql-contrib",
      "required": true
    }
  }
}
```

#### Installation Manager (`install_manager.py`)

The `InstallManager` class handles:

1. **Cloning Apps**: Downloads from git repository
2. **Running Install Scripts**: Executes `install.sh` if present
3. **Dynamic Service Discovery**: Automatically scans for ALL `hivematrix-*` directories with `run.py` files
4. **Service Registry Generation**: Automatically generates both `master_services.json` and `services.json`
5. **Checking Status**: Monitors git status and available updates

**Key Feature - Dynamic Service Discovery:**

The `scan_all_services()` method automatically discovers all HiveMatrix services in the parent directory, not just those in `apps_registry.json`. This makes the system much more flexible:

- **Registry Services**: For services defined in `apps_registry.json`, uses registry metadata (port, name, description)
- **Unknown Services**: For services not in registry (e.g., manually copied or old versions), auto-generates configuration with smart port assignment
- **No Manual Configuration**: After `git pull` or copying a service, it's automatically detected on next startup

**How it works:**
```python
def scan_all_services(self):
    """Scan parent directory for all hivematrix-* services with run.py"""
    discovered = {}

    # Scan for all hivematrix-* directories
    for item in self.parent_dir.iterdir():
        if item.name.startswith('hivematrix-') and (item / 'run.py').exists():
            service_name = item.name.replace('hivematrix-', '')

            # Use registry info if available
            app_info = self.registry.get(service_name)
            if app_info:
                discovered[service_name] = app_info
            else:
                # Auto-generate config for unknown services
                discovered[service_name] = {
                    'name': f'HiveMatrix {service_name.title()}',
                    'port': 5000 + (hash(service_name) % 900),
                    'required': False
                }
    return discovered
```

**Benefits:**
- Copy old service versions → automatically detected
- Git pull new services → automatically registered
- No manual `services.json` edits required
- Works with any `hivematrix-*` service that has `run.py`

**The `update-config` command** reads both the registry AND scans the filesystem to generate service configuration files:

```bash
cd hivematrix-helm
source pyenv/bin/activate

# Install a new service
python install_manager.py install template

# Regenerate service configurations from apps_registry.json
python install_manager.py update-config
```

**When to use `update-config`:**
- After adding a new service to `apps_registry.json`
- After modifying service properties in `apps_registry.json`
- When service configuration files get out of sync
- This is automatically called by `start.sh` on startup

Or via Helm web interface.

#### Required Files for Auto-Installation

For a service to be installable via Helm, it **must** have:

**1. `install.sh`** - Installation script that:
   - Creates Python virtual environment (`python3 -m venv pyenv`)
   - Installs dependencies (`pip install -r requirements.txt`)
   - Creates `instance/` directory
   - Creates initial `.flaskenv` (will be overwritten by config_manager)
   - Symlinks `services.json` from Helm directory
   - Runs any app-specific setup (database creation, etc.)

**2. `requirements.txt`** - Python dependencies:
   ```
   Flask==3.0.0
   python-dotenv==1.0.0
   PyJWT==2.8.0
   cryptography==41.0.7
   SQLAlchemy==2.0.23
   psycopg2-binary==2.9.9
   ```

**3. `run.py`** - Application entry point:
   ```python
   from app import app

   if __name__ == '__main__':
       app.run(debug=True, port=5040, host='0.0.0.0')
   ```

**4. `app/__init__.py`** - Flask app initialization (see Step 1 below)

**5. `services.json` symlink** - Created by install.sh, points to `../hivematrix-helm/services.json`

#### Template install.sh Structure

```bash
#!/bin/bash
set -e  # Exit on error

APP_NAME="template"
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$APP_DIR")"
HELM_DIR="$PARENT_DIR/hivematrix-helm"

# Create virtual environment
python3 -m venv pyenv
source pyenv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create instance directory
mkdir -p instance

# Create initial .flaskenv (will be regenerated by config_manager)
cat > .flaskenv <<EOF
FLASK_APP=run.py
FLASK_ENV=development
SERVICE_NAME=template
CORE_SERVICE_URL=http://localhost:5000
HELM_SERVICE_URL=http://localhost:5004
EOF

# Symlink services.json from Helm
if [ -d "$HELM_DIR" ] && [ -f "$HELM_DIR/services.json" ]; then
    ln -sf "$HELM_DIR/services.json" services.json
fi
```

#### Updating Other Services

To make existing services installable via Helm:

1. **Add to `apps_registry.json`**: Define the service with git URL, port, and dependencies
2. **Create `install.sh`**: Follow the template structure above
3. **Test Installation**: Run `python install_manager.py install <service>`
4. **Update Config**: Ensure config_manager can generate proper .flaskenv and .conf files

**Current Status**: Template is the only fully working installable service. Codex has an install.sh but may need updates. Other services need install scripts created.

## 7. AI Instructions for Building a New Service

All new services (e.g., `Codex`, `Architect`) **must** be created by copying the `hivematrix-template` project. This ensures all necessary patterns are included.

### Step 1: Configuration

Every service requires an `app/__init__.py` that loads its configuration from environment variables (via `.flaskenv`) and config files (via `instance/[service].conf`).

**Important**: The `.flaskenv` file is **automatically generated** by `config_manager.py` from Helm's master configuration. You should not manually edit `.flaskenv` files, as they will be overwritten on the next config sync.

**File: `[new-service]/app/__init__.py` (Example)**

```python
from flask import Flask
import json
import os

app = Flask(__name__, instance_relative_config=True)

# --- Load all required configuration from environment variables ---
# These are set in .flaskenv, which is generated by config_manager.py
app.config['CORE_SERVICE_URL'] = os.environ.get('CORE_SERVICE_URL')
app.config['SERVICE_NAME'] = os.environ.get('SERVICE_NAME', 'myservice')

if not app.config['CORE_SERVICE_URL']:
    raise ValueError("CORE_SERVICE_URL must be set in the .flaskenv file.")

# Load database connection from config file
# This file is generated by config_manager.py
import configparser
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

config_path = os.path.join(app.instance_path, 'myservice.conf')
config = configparser.RawConfigParser()  # Use RawConfigParser for special chars
config.read(config_path)
app.config['MYSERVICE_CONFIG'] = config

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database', 'connection_string',
    fallback=f"sqlite:///{os.path.join(app.instance_path, 'myservice.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Load services configuration for service-to-service calls
# This is symlinked from hivematrix-helm/services.json
try:
    with open('services.json') as f:
        services_config = json.load(f)
        app.config['SERVICES'] = services_config
except FileNotFoundError:
    print("WARNING: services.json not found. Service-to-service calls will not work.")
    app.config['SERVICES'] = {}

from extensions import db
db.init_app(app)

# Apply ProxyFix to handle X-Forwarded headers from Nexus proxy
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # Trust X-Forwarded-For
    x_proto=1,    # Trust X-Forwarded-Proto
    x_host=1,     # Trust X-Forwarded-Host
    x_prefix=1    # Trust X-Forwarded-Prefix (sets SCRIPT_NAME for url_for)
)

from app import routes
```

**Configuration Files (Generated by Helm)**

The following files are **automatically generated** by `config_manager.py`:

**`.flaskenv`** - Generated by `config_manager.py generate_app_dotenv(app_name)`
```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=<auto-generated>
SERVICE_NAME=myservice

# Keycloak Configuration (auto-adjusted for environment)
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_BACKEND_URL=http://localhost:8080
KEYCLOAK_REALM=hivematrix
KEYCLOAK_CLIENT_ID=core-client

# Service URLs
CORE_SERVICE_URL=http://localhost:5000
NEXUS_SERVICE_URL=http://localhost:8000
```

**`instance/myservice.conf`** - Generated by `config_manager.py generate_app_conf(app_name)`
```ini
[database]
connection_string = postgresql://myservice_user:password@localhost:5432/myservice_db
db_host = localhost
db_port = 5432
db_name = myservice_db
db_user = myservice_user
```

To regenerate these files after updating Helm's master config:
```bash
cd hivematrix-helm
source pyenv/bin/activate
python config_manager.py write-dotenv myservice
python config_manager.py write-conf myservice
# Or sync all apps at once:
python config_manager.py sync-all
```

### Step 2: Securing Routes

All routes that display user data or perform actions must be protected by the `@token_required` decorator. This decorator handles JWT verification for both user and service tokens.

**File: `[new-service]/app/auth.py` (Do not modify - copy from template)**

```python
from functools import wraps
from flask import request, g, current_app, abort
import jwt

jwks_client = None

def init_jwks_client():
    """Initializes the JWKS client from the URL in config."""
    global jwks_client
    core_url = current_app.config.get('CORE_SERVICE_URL')
    if core_url:
        jwks_client = jwt.PyJWKClient(f"{core_url}/.well-known/jwks.json")

def token_required(f):
    """
    A decorator to protect routes, ensuring a valid JWT is present.
    This now accepts both user tokens and service tokens.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if jwks_client is None:
            init_jwks_client()

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            abort(401, description="Authorization header is missing or invalid.")

        token = auth_header.split(' ')[1]

        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            data = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer="hivematrix.core",
                options={"verify_exp": True}
            )

            # Determine if this is a user token or service token
            if data.get('type') == 'service':
                # Service-to-service call
                g.user = None
                g.service = data.get('calling_service')
                g.is_service_call = True
            else:
                # User call
                g.user = data
                g.service = None
                g.is_service_call = False

        except jwt.PyJWTError as e:
            abort(401, description=f"Invalid Token: {e}")

        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin permission level."""
    @wraps(f)
    @token_required
    def decorated_function(*args, **kwargs):
        if g.is_service_call:
            # Services can access admin routes
            return f(*args, **kwargs)

        if not g.user or g.user.get('permission_level') != 'admin':
            abort(403, description="Admin access required.")

        return f(*args, **kwargs)
    return decorated_function
```

**File: `[new-service]/app/routes.py` (Example)**

```python
from flask import render_template, g, jsonify
from app import app
from .auth import token_required, admin_required

@app.route('/')
@token_required
def index():
    # Prevent service calls from accessing UI routes
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # The user's information is available in the 'g.user' object
    user = g.user
    return render_template('index.html', user=user)

@app.route('/api/data')
@token_required
def api_data():
    # This endpoint works for both users and services
    if g.is_service_call:
        # Service-to-service call from g.service
        return jsonify({'data': 'service response'})
    else:
        # User call - can check permissions
        if g.user.get('permission_level') != 'admin':
            return {'error': 'Admin only'}, 403
        return jsonify({'data': 'user response'})

@app.route('/admin/settings')
@admin_required
def admin_settings():
    # Only admins can access this
    return render_template('admin/settings.html', user=g.user)
```

### Step 3: Building the UI Template

HTML templates must be unstyled and use the BEM classes from the design system. User data from the JWT is passed into the template.

**File: `[new-service]/app/templates/index.html` (Example)**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My New Service</title>
</head>
<body>
    <div class="card">
        <div class="card__header">
            <h1 class="card__title">Hello, {{ user.name }}!</h1>
        </div>
        <div class="card__body">
            <p>Your username is: <strong>{{ user.preferred_username }}</strong></p>
            <p>Permission level: <strong>{{ user.permission_level }}</strong></p>
            <button class="btn btn--primary">
                <span class="btn__label">Primary Action</span>
            </button>
        </div>
    </div>
</body>
</html>
```

### Step 4: Database Initialization

Create an `init_db.py` script to interactively set up the database:

```python
import os
import sys
import configparser
from getpass import getpass
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import YourModel1, YourModel2  # Import your models

def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("\n--- PostgreSQL Database Configuration ---")

    # Load existing or use defaults
    db_details = {
        'host': config.get('database_credentials', 'db_host', fallback='localhost'),
        'port': config.get('database_credentials', 'db_port', fallback='5432'),
        'user': config.get('database_credentials', 'db_user', fallback='myservice_user'),
        'dbname': config.get('database_credentials', 'db_dbname', fallback='myservice_db')
    }

    host = input(f"Host [{db_details['host']}]: ") or db_details['host']
    port = input(f"Port [{db_details['port']}]: ") or db_details['port']
    dbname = input(f"Database Name [{db_details['dbname']}]: ") or db_details['dbname']
    user = input(f"User [{db_details['user']}]: ") or db_details['user']
    password = getpass("Password: ")

    return {'host': host, 'port': port, 'dbname': dbname, 'user': user, 'password': password}

def test_db_connection(creds):
    """Tests the database connection."""
    from urllib.parse import quote_plus

    escaped_password = quote_plus(creds['password'])
    conn_string = f"postgresql://{creds['user']}:{escaped_password}@{creds['host']}:{creds['port']}/{creds['dbname']}"

    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\n✓ Database connection successful!")
            return conn_string, True
    except Exception as e:
        print(f"\n✗ Connection failed: {e}", file=sys.stderr)
        return None, False

def init_db():
    """Interactively configures and initializes the database."""
    instance_path = app.instance_path
    config_path = os.path.join(instance_path, 'myservice.conf')

    config = configparser.RawConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)
        print(f"\n✓ Existing configuration found: {config_path}")
    else:
        print(f"\n→ Creating new config: {config_path}")
        os.makedirs(instance_path, exist_ok=True)

    # Database configuration
    while True:
        creds = get_db_credentials(config)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)

            if not config.has_section('database_credentials'):
                config.add_section('database_credentials')
            for key, val in creds.items():
                if key != 'password':
                    config.set('database_credentials', f'db_{key}', val)
            break
        else:
            if input("\nRetry? (y/n): ").lower() != 'y':
                sys.exit("Database configuration aborted.")

    # Save configuration
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print(f"\n✓ Configuration saved to: {config_path}")

    # Initialize database schema
    with app.app_context():
        print("\nInitializing database schema...")
        db.create_all()
        print("✓ Database schema initialized successfully!")

if __name__ == '__main__':
    init_db()
```

## 8. Running the Development Environment

HiveMatrix provides a unified startup script that handles installation, configuration, and service orchestration.

### Quick Start

From the `hivematrix-helm` directory:

```bash
./start.sh
```

This script will:
1. Check and install system dependencies (Python, Git, Java, PostgreSQL)
2. Download and setup Keycloak
3. Clone and install Core and Nexus if not present
4. Setup databases
5. **Auto-detect and register all services** (via `install_manager.py update-config`)
6. **Automatically configure Keycloak** realm and users (if needed)
7. Sync configurations to all apps (via `config_manager.py`)
8. Start all services (Keycloak, Core, Nexus, and any additional installed apps)
9. Launch Helm web interface on port 5004

### Keycloak Auto-Configuration

HiveMatrix includes intelligent Keycloak setup automation that ensures proper synchronization between Keycloak and the system configuration.

**Automatic Configuration Detection:**

The startup script (`start.sh`) automatically detects when Keycloak needs to be configured by checking:

1. **Fresh Keycloak Installation**: If Keycloak was just downloaded (directory didn't exist)
2. **Missing Configuration**: If `client_secret` is missing from `master_config.json`
3. **Configuration Sync**: If `master_config.json` is missing but Keycloak exists, it removes Keycloak to force reinstallation

**What Gets Configured:**

When Keycloak configuration runs (`configure_keycloak.sh`), it creates:

- **Realm**: `hivematrix` realm with proper frontend URL settings
- **Client**: `core-client` with OAuth2 authorization code flow
- **Admin User**: Default admin user (`admin`/`admin`)
- **Permission Groups**:
  - `admins` - Full system access
  - `technicians` - Technical operations
  - `billing` - Financial operations
  - `client` - Limited access (default for new users)
- **Group Mapper**: OIDC mapper to include group membership in JWT tokens

**Configuration Synchronization:**

The system maintains synchronization between Keycloak and `master_config.json`:

```bash
# If Keycloak is reinstalled (directory deleted)
1. Start.sh detects Keycloak is missing
2. Downloads and extracts Keycloak
3. Clears old keycloak section from master_config.json
4. Runs configure_keycloak.sh to set up realm and users
5. Saves new client_secret to master_config.json

# If master_config.json is deleted but Keycloak exists
1. Start.sh detects config is missing
2. Removes Keycloak directory to force clean state
3. Re-downloads Keycloak
4. Runs full configuration
```

**Manual Reconfiguration:**

To force Keycloak reconfiguration:

```bash
# Delete Keycloak directory - will trigger full reinstall and config
rm -rf ../keycloak-26.4.0
./start.sh

# Or delete master config - will force resync
rm instance/configs/master_config.json
./start.sh
```

**Keycloak Configuration Files:**

- **Master Config**: `hivematrix-helm/instance/configs/master_config.json` - Stores `client_secret` and URLs
- **Service Configs**: Each service's `.flaskenv` gets Keycloak settings from master config
- **Keycloak Config**: `../keycloak-26.4.0/conf/keycloak.conf` - Auto-configured for proxy mode with hostname

The configuration process is **idempotent** - running it multiple times is safe and will update existing configurations rather than creating duplicates

### Development Mode

For development with Flask's auto-reload:

```bash
./start.sh --dev
```

This uses Flask's development server instead of Gunicorn.

### Manual Service Management

You can also manage services individually using the Helm CLI:

```bash
cd hivematrix-helm
source pyenv/bin/activate

# Start individual services
python cli.py start keycloak
python cli.py start core
python cli.py start nexus
python cli.py start template

# Check service status
python cli.py status

# Stop services
python cli.py stop template
python cli.py stop nexus
python cli.py stop core
python cli.py stop keycloak

# Restart a service
python cli.py restart core
```

### Access Points

After running `./start.sh`, access the platform at:

- **HiveMatrix**: `https://localhost:443` (or `http://localhost:8000` if port 443 binding failed)
- **Helm Dashboard**: `http://localhost:5004`
- **Keycloak Admin**: `http://localhost:8080`
- **Core Service**: `http://localhost:5000`

Default credentials:
- Username: `admin`
- Password: `admin`

**Important**: Change the default password in Keycloak admin console after first login.

### Installing Additional Services

Via Helm web interface (http://localhost:5004):
1. Navigate to "Apps" or "Services" section
2. Click "Install" next to the desired service
3. Wait for installation to complete
4. Service will automatically start

Via command line:
```bash
cd hivematrix-helm
source pyenv/bin/activate
python install_manager.py install codex
python cli.py start codex
```

### Configuration Updates

After modifying Helm's master configuration, sync to all apps:

```bash
cd hivematrix-helm
source pyenv/bin/activate
python config_manager.py sync-all
```

Or restart the platform with `./start.sh` which automatically syncs configs.

## 9. Development & Debugging Tools

HiveMatrix includes CLI tools in the `hivematrix-helm` repository to streamline development and debugging workflows. These tools eliminate the need to manually navigate web interfaces or query databases during development.

### Centralized Logging System

All HiveMatrix services send logs to Helm's PostgreSQL database for centralized storage and analysis. This allows viewing logs from all services in one place.

### logs_cli.py - View Service Logs

Quick command-line access to centralized logs from any service.

**Usage:**
```bash
cd hivematrix-helm
source pyenv/bin/activate

# View recent logs from a specific service
python logs_cli.py knowledgetree --tail 50

# Filter by log level
python logs_cli.py core --level ERROR --tail 100

# View all services
python logs_cli.py --tail 30
```

**Features:**
- Color-coded output by log level (ERROR=red, WARNING=yellow, INFO=green, DEBUG=blue)
- Filters by service name and log level
- Configurable tail count
- Reads directly from Helm's PostgreSQL database

**Implementation:**
- Location: `hivematrix-helm/logs_cli.py`
- Database: Reads from `log_entries` table in Helm's PostgreSQL database
- Config: Uses `instance/helm.conf` for database connection

### create_test_token.py - Generate JWT Tokens

Creates valid JWT tokens for testing authenticated endpoints without browser login.

**Usage:**
```bash
cd hivematrix-helm
source pyenv/bin/activate

# Generate a test token
TOKEN=$(python create_test_token.py 2>/dev/null)

# Use token to test an endpoint
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5020/knowledgetree/browse/
```

**Features:**
- Generates tokens signed with Core's RSA private key
- Creates admin-level user tokens with 24-hour expiration
- Includes proper JWT headers (kid, alg) matching Core's JWKS
- No server interaction required - works offline

**Token Payload:**
```json
{
  "sub": "admin",
  "username": "admin",
  "preferred_username": "admin",
  "email": "admin@hivematrix.local",
  "permission_level": "admin",
  "iss": "hivematrix-core",
  "groups": ["admin"],
  "exp": "<24_hours_from_now>"
}
```

**Implementation:**
- Location: `hivematrix-helm/create_test_token.py`
- Requires: Core's private key at `../hivematrix-core/keys/jwt_private.pem`
- Output: Raw JWT token to stdout

### test_with_token.sh - Quick Endpoint Testing

Convenience wrapper that generates a token and tests an endpoint in one command.

**Usage:**
```bash
cd hivematrix-helm

# Test KnowledgeTree browse endpoint
./test_with_token.sh

# Or modify to test any endpoint:
# Edit test_with_token.sh and change the curl URL
```

**Script Contents:**
```bash
#!/bin/bash
cd /home/david/Work/hivematrix/hivematrix-helm
source pyenv/bin/activate
TOKEN=$(python create_test_token.py 2>/dev/null)

echo "Testing KnowledgeTree /browse with auth token..."
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5020/knowledgetree/browse/
```

### Development Workflow

**Debugging a Service Error:**

1. **Check Recent Logs:**
   ```bash
   cd hivematrix-helm
   source pyenv/bin/activate
   python logs_cli.py myservice --tail 50
   ```

2. **Test Authenticated Endpoint:**
   ```bash
   TOKEN=$(python create_test_token.py 2>/dev/null)
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5010/myservice/api/data | jq
   ```

3. **Monitor Logs During Testing:**
   ```bash
   # Terminal 1: Watch logs
   watch -n 2 'python logs_cli.py myservice --tail 20'

   # Terminal 2: Make test requests
   ./test_with_token.sh
   ```

**Testing Service-to-Service Communication:**

```bash
# Generate token and test from calling service
TOKEN=$(python create_test_token.py 2>/dev/null)

# Simulate service call to target service
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://127.0.0.1:5010/codex/api/companies
```

### Adding Logging to Your Service

All services should use the Helm logger for centralized logging:

**In your service's `app/__init__.py`:**
```python
from app.helm_logger import init_helm_logger

# Initialize logger
app.config["SERVICE_NAME"] = os.environ.get("SERVICE_NAME", "myservice")
app.config["HELM_SERVICE_URL"] = os.environ.get("HELM_SERVICE_URL", "http://localhost:5004")

helm_logger = init_helm_logger(
    app.config["SERVICE_NAME"],
    app.config["HELM_SERVICE_URL"]
)

# Log service startup
helm_logger.info(f"{app.config['SERVICE_NAME']} service started")
```

**In your routes:**
```python
from app import helm_logger

@app.route('/api/data')
@token_required
def api_data():
    try:
        helm_logger.info("Fetching data", extra={'user': g.user.get('username')})
        # ... your code ...
        return jsonify({'data': result})
    except Exception as e:
        helm_logger.error(f"Failed to fetch data: {e}", exc_info=True)
        return {'error': 'Internal error'}, 500
```

### Troubleshooting Tools

**Check if logs are being stored:**
```bash
cd hivematrix-helm
source pyenv/bin/activate
python -c "
import psycopg2
import configparser

config = configparser.ConfigParser()
config.read('instance/helm.conf')
conn_str = config.get('database', 'connection_string')

conn = psycopg2.connect(conn_str)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM log_entries')
print(f'Total logs: {cursor.fetchone()[0]}')
conn.close()
"
```

**Clear old logs:**
```bash
# Not yet implemented - logs currently accumulate
# TODO: Add log rotation/cleanup tool
```

## 10. Security Architecture

HiveMatrix follows a **zero-trust internal network model** where only the Nexus gateway should be accessible externally. All other services operate on localhost and are accessed through the Nexus proxy.

### Security Principles

1. **Single Entry Point**: Only port 443 (Nexus with HTTPS) should be exposed externally
2. **Localhost Binding**: All backend services (Core, Keycloak, apps) bind to 127.0.0.1
3. **Proxy Access**: All services are accessed via Nexus proxy with authentication
4. **Firewall Protection**: Host firewall blocks direct access to internal services
5. **Automated Auditing**: Security checks run automatically on startup

### Service Binding Requirements

**Backend Services (bind to localhost only):**
```python
# Correct - secure binding
app.run(host='127.0.0.1', port=5040)
```

Services that MUST bind to localhost:
- Keycloak (8080)
- Core (5000)
- Helm (5004)
- All application services (Codex, Ledger, Template, etc.)

**Frontend Gateway (bind to all interfaces):**
```python
# Nexus - public entry point
app.run(host='0.0.0.0', port=443)
```

Only Nexus (443) should bind to `0.0.0.0` as it's the authenticated entry point.

### Security Audit Tool

Helm includes a security audit tool that checks service port bindings:

```bash
cd hivematrix-helm
source pyenv/bin/activate
python security_audit.py --audit
```

This automatically runs during `./start.sh` and reports:
- ✓ Services properly bound to localhost
- ✗ Services exposed to network (security risk)
- ○ Services not running

### Firewall Configuration

Generate and apply firewall rules to block direct access to internal services:

```bash
# Generate firewall script
python security_audit.py --generate-firewall

# Apply firewall rules (requires sudo)
sudo bash secure_firewall.sh
```

This configures Ubuntu's UFW firewall to:
- Allow SSH (port 22)
- Allow HTTPS (port 443 - Nexus)
- Block all internal service ports from external access

**Alternative with iptables:**
```bash
python security_audit.py --generate-iptables
sudo bash secure_iptables.sh
```

### Security Checklist

Before deploying to production:

- [ ] Run security audit: `python security_audit.py --audit`
- [ ] All services bound to localhost (except Nexus on 443)
- [ ] Firewall configured and enabled
- [ ] Change default Keycloak admin password
- [ ] Change default HiveMatrix admin password
- [ ] Use valid SSL certificate (not self-signed) for Nexus
- [ ] Review Keycloak security settings
- [ ] Test external access blocked
- [ ] Test internal access via Nexus works

### Common Security Issues

**Issue: Service exposed to network**

Symptom: Security audit shows service on `0.0.0.0` instead of `127.0.0.1`

Fix: Update service's `run.py` to bind to localhost:
```python
# Change from:
app.run(host='0.0.0.0', port=5040)

# To:
app.run(host='127.0.0.1', port=5040)
```

**Issue: Keycloak exposed**

Keycloak (Java-based) may bind to all interfaces. This is acceptable if protected by firewall. The security audit will flag this - apply firewall rules to block external access:
```bash
sudo bash secure_firewall.sh
```

**Issue: Can't access service after fixing binding**

This is expected behavior! Services on localhost are accessed via:
- **Internal**: `http://localhost:PORT` (from server)
- **External**: `https://SERVER_IP:443/service-name` (via Nexus proxy)

Never access services directly by their port. Always use Nexus.

### Production Deployment Security

Additional security measures for production:

1. **SSL Certificates**: Use Let's Encrypt or commercial SSL for Nexus
2. **Fail2ban**: Protect SSH from brute force attacks
3. **Rate Limiting**: Configure in Nexus or load balancer
4. **Security Updates**: Regular system and application updates
5. **Monitoring**: Log analysis and intrusion detection
6. **Backups**: Regular encrypted backups of databases and configs

See `SECURITY.md` for detailed security configuration and best practices.

## 10. Design System & BEM Classes

_(This section will be expanded with more components as they are built.)_

### Component: Card (`.card`)

-   **Block:** `.card` - The main container.
-   **Elements:** `.card__header`, `.card__title`, `.card__body`

### Component: Button (`.btn`)

-   **Block:** `.btn`
-   **Elements:** `.btn__icon`, `.btn__label`
-   **Modifiers:** `.btn--primary`, `.btn--danger`

### Component: Table

-   **Block:** `table` - Standard HTML table element
-   **Elements:** `thead`, `tbody`, `th`, `td`
-   Styling is provided globally by Nexus

### Component: Form Elements

-   **Input:** Standard `input`, `select`, `textarea` elements
-   **Label:** Standard `label` element
-   Styling is provided globally by Nexus

## 11. Database Best Practices

### Configuration Storage

- Use `configparser.RawConfigParser()` instead of `ConfigParser()` to handle special characters in passwords
- Store database credentials in `instance/[service].conf`
- Never commit config files to version control (they're in `.gitignore`)

### Models

- Each service owns its own database tables
- Use SQLAlchemy for ORM
- Define models in `models.py`
- Use appropriate data types:
  - `db.String(50)` for short strings (IDs, codes)
  - `db.String(150)` for names
  - `db.String(255)` for URLs, domains
  - `db.Text` for long text fields
  - `BigInteger` for large numeric IDs (like Freshservice IDs)

### Relationships

- Use association tables for many-to-many relationships
- Use `db.relationship()` with `back_populates` for bidirectional relationships
- Add `cascade="all, delete-orphan"` for proper cleanup

## 12. External System Integration

### Sync Scripts

Services that integrate with external systems (like Codex with Freshservice and Datto) should:

- Have standalone Python scripts (e.g., `pull_freshservice.py`, `pull_datto.py`)
- Import the Flask app and models directly
- Use the app context: `with app.app_context():`
- Be runnable via cron for automated syncing
- Include proper error handling and logging

### API Credentials

- Store API credentials in the service's config file
- Never hardcode credentials
- Provide interactive setup via `init_db.py`

## 13. Common Patterns

### Service Directory Structure

```
hivematrix-myservice/
├── app/
│   ├── __init__.py           # Flask app initialization
│   ├── auth.py               # @token_required decorator
│   ├── routes.py             # Main web routes
│   ├── service_client.py     # Service-to-service helper
│   ├── middleware.py         # URL prefix middleware
│   └── templates/            # HTML templates (BEM styled)
│       └── admin/            # Admin-only templates
├── routes/                   # Blueprint routes (optional)
│   ├── __init__.py
│   ├── entities.py
│   └── admin.py
├── instance/
│   └── myservice.conf        # Configuration (not in git)
├── extensions.py             # Flask extensions (db)
├── models.py                 # SQLAlchemy models
├── init_db.py                # Database initialization script
├── run.py                    # Application entry point
├── services.json             # Service discovery config (symlinked from Helm)
├── requirements.txt          # Python dependencies
├── .flaskenv                 # Environment variables (not in git)
├── .gitignore
└── README.md
```

### Required Files

Every service must have:
- `.flaskenv` - Environment configuration
- `requirements.txt` - Python dependencies
- `run.py` - Entry point
- `app/__init__.py` - Flask app setup
- `app/auth.py` - Authentication decorators (copy from template)
- `app/service_client.py` - Service-to-service helper (copy from template)
- `app/middleware.py` - URL prefix middleware (copy from template)
- `extensions.py` - Flask extensions
- `models.py` - Database models
- `init_db.py` - Interactive database setup
- `services.json` - Service discovery (symlinked to `../hivematrix-helm/services.json`)

**Note:** The `services.json` file should be a symlink created by `install.sh`, not a regular file. This ensures all services see the same service registry.

### Service Configuration Files in Helm

Helm maintains **two** service configuration files with different purposes:

**1. `master_services.json`** - Minimal service registry
- **Purpose:** Used by Nexus for service discovery and URL routing
- **Format:** Simplified with just `url` and `port`
- **Synced to:** Individual services via service_manager
- **When to update:** When adding/removing services

**2. `services.json`** - Complete service configuration
- **Purpose:** Used by Helm for service management (start/stop/status)
- **Format:** Extended with `path`, `python_bin`, `run_script`, `visible`
- **Used by:** Helm's service_manager.py and cli.py
- **When to update:** When adding/removing services

**Adding a new service workflow:**

Instead of manually editing both `master_services.json` and `services.json`, you should:

1. **Add the service to `apps_registry.json`:**
   ```json
   {
     "default_apps": {
       "archive": {
         "name": "HiveMatrix Archive",
         "description": "Document and file archival system",
         "git_url": "https://github.com/ruapotato/hivematrix-archive",
         "port": 5012,
         "required": false,
         "dependencies": ["core", "codex"],
         "install_order": 8
       }
     }
   }
   ```

2. **Run `update-config` to generate both files automatically:**
   ```bash
   cd hivematrix-helm
   source pyenv/bin/activate
   python install_manager.py update-config
   ```

This will automatically create entries in both `master_services.json` and `services.json`:

**Generated `master_services.json` entry:**
```json
{
  "archive": {
    "url": "http://localhost:5012",
    "port": 5012
  }
}
```

**Generated `services.json` entry:**
```json
{
  "archive": {
    "url": "http://localhost:5012",
    "path": "../hivematrix-archive",
    "port": 5012,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true
  }
}
```

**Important:** Always use `apps_registry.json` as the source of truth and let `install_manager.py update-config` generate the other files. Manual edits to `services.json` or `master_services.json` will be overwritten on the next config update.

## 14. Brainhair AI Assistant & Approval Flow

**Brainhair** is the AI assistant service that enables natural language interaction with the HiveMatrix platform. It provides Claude AI integration for performing administrative tasks, answering questions, and managing system operations.

**Design Goal:** Brainhair should be able to manage **everything** in the HiveMatrix platform. Any administrative task that can be performed through the web interface should also be accessible via natural language commands through Brainhair. This includes creating, reading, updating, and deleting data across all services (Codex, Ledger, Resolve, Archive, etc.).

### Architecture

Brainhair consists of:
- **Web Interface** (port 5050): Chat interface for Claude AI conversations
- **AI Tools**: Python scripts in `ai_tools/` directory that perform system operations
- **Approval System**: User approval mechanism for write operations

### AI Tools Pattern

AI tools are standalone Python scripts that:
1. Accept command-line arguments for parameters
2. Use service-to-service authentication to call other HiveMatrix APIs
3. Request user approval before performing write operations
4. Print results to stdout for the AI to parse

**Example Tool Structure:**
```python
#!/path/to/pyenv/bin/python
"""
Tool Description

Usage:
    python tool_name.py <company> <action>
"""

import sys
import os
import requests

# Import approval helper for write operations
sys.path.insert(0, os.path.dirname(__file__))
from approval_helper import request_approval

# Service URLs from environment
CORE_URL = os.getenv('CORE_SERVICE_URL', 'http://localhost:5000')
LEDGER_URL = os.getenv('LEDGER_SERVICE_URL', 'http://localhost:5030')

def get_service_token(target_service):
    """Get service token from Core for API calls."""
    response = requests.post(
        f"{CORE_URL}/service-token",
        json={
            "calling_service": "brainhair",
            "target_service": target_service
        }
    )
    return response.json()["token"]

def perform_action(data):
    """Perform the action (read-only operation)."""
    token = get_service_token("ledger")
    response = requests.get(
        f"{LEDGER_URL}/api/data",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

def main():
    # Parse arguments
    # ... argument parsing ...

    # For write operations, request approval first
    approved = request_approval(
        "Action description",
        {
            'Company': company_name,
            'Field': 'Value',
            'Amount': '$100.00'
        }
    )

    if not approved:
        print("✗ User denied the change")
        sys.exit(1)

    # Perform the approved action
    result = perform_action(data)
    print(f"✓ Action completed: {result}")

if __name__ == "__main__":
    main()
```

### Approval Flow for Write Operations

**Critical Rule:** All AI tools that perform write operations (create, update, delete) **must** request user approval before executing the change.

#### How Approval Works

The approval system uses a file-based IPC (Inter-Process Communication) mechanism to enable real-time user approval in the browser while the tool waits for a response.

**Flow:**
1. **Tool requests approval**: Calls `request_approval(action, details)`
2. **File creation**: Creates `/tmp/brainhair_approval_request_{session_id}_{timestamp}.json`
3. **Browser detection**: Chat polling endpoint finds the approval file
4. **Modal display**: Browser shows approval dialog with action details
5. **User decision**: User clicks "Approve" or "Deny"
6. **Response file**: Browser writes `/tmp/brainhair_approval_response_{approval_id}.json`
7. **Tool reads response**: Tool polls for response file and continues/exits based on decision

#### Approval Helper (`ai_tools/approval_helper.py`)

```python
def request_approval(action: str, details: dict, timeout: int = 120) -> bool:
    """
    Request user approval for a write operation.

    Args:
        action: Description of the action (e.g., "Update billing rates for Company X")
        details: Dictionary of details to show user (e.g., {'Company': 'X', 'Amount': '$100'})
        timeout: Maximum seconds to wait for user response (default: 120)

    Returns:
        True if user approved, False if denied or timeout
    """
    session_id = os.environ.get('BRAINHAIR_SESSION_ID')
    approval_id = f"{session_id}_{int(time.time() * 1000)}"

    # Write approval request file
    request_file = f"/tmp/brainhair_approval_request_{approval_id}.json"
    with open(request_file, 'w') as f:
        json.dump({
            'type': 'approval_request',
            'approval_id': approval_id,
            'session_id': session_id,
            'action': action,
            'details': details
        }, f)

    # Poll for response file
    response_file = f"/tmp/brainhair_approval_response_{approval_id}.json"
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(response_file):
            with open(response_file, 'r') as f:
                response = json.load(f)

            # Cleanup
            os.remove(request_file)
            os.remove(response_file)

            return response.get('approved', False)

        time.sleep(0.5)

    # Timeout - cleanup and return False
    if os.path.exists(request_file):
        os.remove(request_file)

    return False
```

#### Browser Integration

The chat interface polls for approval requests and handles user responses:

```javascript
// In chat polling loop
if (chunk.type === 'approval_request') {
    showApprovalDialog(chunk);
}

function showApprovalDialog(approvalData) {
    // Show modal with action and details
    document.getElementById('approval-action').textContent = approvalData.action;

    // Populate details table
    const detailsTable = document.getElementById('approval-details');
    for (const [key, value] of Object.entries(approvalData.details)) {
        // Add row for each detail
    }

    // Show modal
    document.getElementById('approval-dialog').style.display = 'block';
}

function respondToApproval(approved) {
    // Write response file
    fetch('/api/chat/approval-response', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            approval_id: currentApprovalId,
            approved: approved
        })
    });

    // Hide modal
    document.getElementById('approval-dialog').style.display = 'none';
}
```

#### Tools That Require Approval

**Write operations** that modify data:
- `update_billing.py` - Change billing rates and add line items
- `set_company_plan.py` - Assign/change company billing plans
- `manage_network_equipment.py` - Add/remove network equipment
- `update_features.py` - Modify feature overrides

**Read operations** that do NOT require approval:
- `list_companies.py` - View company data
- `view_billing.py` - Display billing information
- `get_company_plan.py` - Show current plan details

### Environment Variables

Brainhair sets environment variables for tools:
- `BRAINHAIR_SESSION_ID`: Current chat session ID for approval tracking
- `CORE_SERVICE_URL`: Core service URL for token requests
- `LEDGER_SERVICE_URL`: Ledger service URL
- `CODEX_SERVICE_URL`: Codex service URL

### Adding New AI Tools

When creating a new AI tool:

1. **Read-only tool:** No special requirements, just query APIs and print results
2. **Write tool:** Must use approval_helper:
   ```python
   from approval_helper import request_approval

   approved = request_approval(
       "Clear, concise action description",
       {
           'Detail 1': 'value',
           'Detail 2': 'value'
       }
   )

   if not approved:
       print("✗ User denied the change")
       sys.exit(1)
   ```
3. Make executable: `chmod +x ai_tools/your_tool.py`
4. Add shebang: `#!/path/to/brainhair/pyenv/bin/python`
5. Document usage in docstring

### PHI/CJIS Filtering

**Critical Security Feature:** Brainhair implements automatic PHI (Protected Health Information) and CJIS (Criminal Justice Information Systems) data filtering to prevent sensitive information from being exposed to the AI or logged inappropriately.

#### How Filtering Works

Brainhair uses **Microsoft Presidio** for automated detection and anonymization of sensitive data in tool responses. All data that flows through Brainhair's API endpoints is automatically filtered before being sent to Claude or displayed to users.

**Filtered Entity Types:**

**PHI Entities:**
- PERSON (names) - Anonymized to "FirstName L." format
- EMAIL_ADDRESS - Replaced with `<EMAIL_ADDRESS>`
- PHONE_NUMBER - Replaced with `<PHONE_NUMBER>`
- US_SSN - Replaced with `<US_SSN>`
- DATE_TIME - Replaced with `<DATE_TIME>`
- LOCATION - Replaced with `<LOCATION>`
- MEDICAL_LICENSE - Replaced with `<MEDICAL_LICENSE>`
- US_DRIVER_LICENSE - Replaced with `<US_DRIVER_LICENSE>`
- US_PASSPORT - Replaced with `<US_PASSPORT>`
- CREDIT_CARD - Replaced with `<CREDIT_CARD>`
- IP_ADDRESS - Replaced with `<IP_ADDRESS>`

**CJIS Entities:**
- PERSON, US_SSN, US_DRIVER_LICENSE, DATE_TIME, LOCATION, IP_ADDRESS

#### Filtering in AI Tools

AI tools automatically apply PHI filtering when querying data from other services:

```python
# Example: list_tickets.py
def list_tickets(source="codex", company_id=None, status=None, filter_type="phi", limit=50):
    """
    List tickets with PHI/CJIS filtering.

    Args:
        filter_type: Type of filter to apply ("phi" or "cjis")
    """
    auth = get_auth()

    # Filter parameter is automatically applied by Brainhair API
    params = {"filter": filter_type}

    response = auth.get("/api/codex/tickets", params=params)
    # Response data is already filtered by Brainhair
```

When an AI tool calls a Brainhair API endpoint with `?filter=phi` or `?filter=cjis`, the response is automatically filtered before being returned.

#### Presidio Filter Implementation

The filtering is handled by `app/presidio_filter.py`:

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

class PresidioFilter:
    def filter_phi(self, data):
        """Filter PHI from data (dict, list, or str)"""
        # Analyzes text for PHI entities
        # Anonymizes detected entities
        # Returns filtered data

    def filter_cjis(self, data):
        """Filter CJIS data from data"""
        # Similar to PHI but with CJIS entity types
```

#### Example: Before and After Filtering

**Before filtering:**
```json
{
  "requester": "John Smith",
  "email": "john.smith@example.com",
  "phone": "555-123-4567",
  "description": "Need help with SSN 123-45-6789",
  "ip_address": "192.168.1.100"
}
```

**After PHI filtering:**
```json
{
  "requester": "John S.",
  "email": "<EMAIL_ADDRESS>",
  "phone": "<PHONE_NUMBER>",
  "description": "Need help with SSN <US_SSN>",
  "ip_address": "<IP_ADDRESS>"
}
```

#### Custom Anonymizers

Brainhair includes custom anonymization operators:
- **FirstNameLastInitialOperator**: Converts "John Smith" to "John S." (preserves first name, shows last initial)
- This provides better context for the AI while still protecting identity

#### When to Use Each Filter

- **PHI Filter** (default): Use for healthcare, MSP client data, general user information
- **CJIS Filter**: Use for law enforcement, criminal justice, government systems data

**Tools that use filtering:**
- `list_tickets.py` - Filters ticket data
- `list_companies.py` - Filters company contact information
- `list_devices.py` - Filters device and user data
- `search_knowledge.py` - Filters knowledge base content

#### Disabling Filtering (Advanced)

Filtering can be bypassed by passing `filter=none` in API requests, but this should only be done:
1. For internal system operations that require full data
2. When the user has proper authorization
3. In controlled environments where PHI exposure is acceptable

**Most AI tools should always use PHI filtering by default.**

### Security Considerations

- Tools run with **service-level authentication** (bypass user permission checks)
- Approval system ensures human oversight for all write operations
- Session ID tracking prevents cross-session approval hijacking
- Timeout prevents tools from hanging indefinitely (default: 120 seconds)
- Approval files are cleaned up after use to prevent file system bloat
- **PHI/CJIS filtering** prevents sensitive data exposure to AI and logs

### Debugging

View Brainhair logs:
```bash
cd hivematrix-helm
source pyenv/bin/activate
python logs_cli.py brainhair --tail 50
```

Test approval flow:
```bash
# Set session ID (get from browser console)
export BRAINHAIR_SESSION_ID="session_abc123"

# Run tool manually
cd hivematrix-brainhair
./ai_tools/update_billing.py "Company Name" --per-user 100
```

Check for approval files:
```bash
ls -la /tmp/brainhair_approval_*
```

## 15. Version History

- **4.0** - **Brainhair AI Assistant & Approval Flow**: Added comprehensive documentation for Brainhair AI assistant service including AI tools pattern, approval flow for write operations, file-based IPC mechanism, browser integration, PHI/CJIS filtering with Microsoft Presidio, security considerations, and debugging guides. All write operations in AI tools (update_billing.py, set_company_plan.py, manage_network_equipment.py, update_features.py) now require explicit user approval before execution via approval_helper.py. Automatic PHI filtering protects sensitive information in tool responses using Presidio entity detection and anonymization.

- **3.9** - **Dynamic Service Discovery & Keycloak Auto-Configuration**: Added `scan_all_services()` to `install_manager.py` for automatic detection of all `hivematrix-*` services (not just registry). Services are discovered on every `start.sh` run, allowing manual copies and git pulls to work seamlessly. Enhanced Keycloak setup with intelligent synchronization between Keycloak database and `master_config.json` - tracks fresh Keycloak installations (`KEYCLOAK_FRESH_INSTALL`), clears old config when reinstalling, and ensures realm/users are always configured. Two-way sync prevents configuration drift. Both improvements make the system more resilient and reduce manual configuration.

- **3.8** - Documented apps_registry.json as the authoritative source for service configuration, with install_manager.py update-config generating both master_services.json and services.json automatically. Added archive service example to registry documentation.

- **3.7** - Documented master_services.json and services.json dual configuration system for service discovery and management

- **3.6** - Updated URL prefix handling to use werkzeug's ProxyFix middleware instead of custom PrefixMiddleware. Added X-Forwarded-Prefix header from Nexus. Documented cookie-based authentication fallback for AJAX requests with credentials: 'same-origin'.
- **3.5** - Added Development & Debugging Tools section: logs_cli.py for centralized log viewing, create_test_token.py for JWT token generation, test_with_token.sh for quick endpoint testing, and comprehensive debugging workflows
- **3.4** - Added comprehensive security architecture, security audit tool (security_audit.py), firewall generation, service binding requirements, and automated security checks in start.sh
- **3.3** - Added centralized configuration management (config_manager.py), auto-installation architecture (install_manager.py), unified startup script (start.sh), and comprehensive deployment documentation
- **3.2** - Added revokable session management, logout flow, token validation, Keycloak proxy on port 443
- **3.1** - Added service-to-service communication, permission levels, database best practices, external integrations
- **3.0** - Initial version with core architecture patterns
