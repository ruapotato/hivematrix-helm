# HiveMatrix Architecture & AI Development Guide

**Version 3.3**

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

Services are registered in `services.json` for discovery:

```json
{
  "codex": {
    "url": "http://localhost:5010"
  },
  "treasury": {
    "url": "http://localhost:5011"
  }
}
```

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

### URL Prefix Middleware

Each service must handle URL prefixes when behind the Nexus proxy. The `PrefixMiddleware` class adjusts the WSGI environment:

```python
# In app/__init__.py
from app.middleware import PrefixMiddleware
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=f'/{app.config["SERVICE_NAME"]}')
```

This allows services to generate correct URLs using Flask's `url_for()` when accessed through Nexus.

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

All installable apps are defined in `hivematrix-helm/apps_registry.json`:

```json
{
  "core_apps": {
    "core": {
      "name": "HiveMatrix Core",
      "git_url": "https://github.com/ruapotato/hivematrix-core",
      "port": 5000,
      "required": true,
      "dependencies": ["postgresql"],
      "install_order": 1
    }
  },
  "default_apps": {
    "template": {
      "name": "HiveMatrix Template",
      "git_url": "https://github.com/ruapotato/hivematrix-template",
      "port": 5040,
      "required": false,
      "dependencies": ["core"],
      "install_order": 6
    }
  }
}
```

#### Installation Manager (`install_manager.py`)

The `InstallManager` class handles:

1. **Cloning Apps**: Downloads from git repository
2. **Running Install Scripts**: Executes `install.sh` if present
3. **Updating Service Registry**: Adds app to `services.json` for service discovery
4. **Checking Status**: Monitors git status and available updates

Installation flow:
```bash
cd hivematrix-helm
source pyenv/bin/activate
python install_manager.py install template
```

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

# Apply middleware to handle URL prefix when behind Nexus proxy
from app.middleware import PrefixMiddleware
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=f'/{app.config["SERVICE_NAME"]}')

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
5. Configure Keycloak realm and users
6. Sync configurations to all apps (via `config_manager.py`)
7. Start all services (Keycloak, Core, Nexus, and any additional installed apps)
8. Launch Helm web interface on port 5004

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

## 9. Design System & BEM Classes

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

## 10. Database Best Practices

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

## 11. External System Integration

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

## 12. Common Patterns

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
├── services.json             # Service discovery config
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
- `services.json` - Service discovery

## 13. Version History

- **3.3** - Added centralized configuration management (config_manager.py), auto-installation architecture (install_manager.py), unified startup script (start.sh), and comprehensive deployment documentation
- **3.2** - Added revokable session management, logout flow, token validation, Keycloak proxy on port 443
- **3.1** - Added service-to-service communication, permission levels, database best practices, external integrations
- **3.0** - Initial version with core architecture patterns
