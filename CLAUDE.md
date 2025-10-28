# Claude AI Assistant Guidelines for HiveMatrix

**VERSION:** 2.0
**LAST UPDATED:** 2025-10-28

---

## 🚨 CRITICAL: READ THIS FIRST

**BEFORE doing ANYTHING else, you MUST read the complete ARCHITECTURE.md file:**

```bash
# Location: /home/troy/projects/hivematrix/hivematrix-helm/ARCHITECTURE.md
```

**ARCHITECTURE.md is the single source of truth for this project.** All patterns, conventions, and design decisions are documented there. Violating the architecture will break the system.

**Do NOT:**
- Skip reading ARCHITECTURE.md
- Assume standard patterns (this project has specific requirements)
- Use custom middleware when ProxyFix is specified
- Add styling to service templates (Nexus injects global CSS)
- Access another service's database directly
- Commit changes without understanding the auth flow

**Every time you start a new task, re-read relevant sections of ARCHITECTURE.md.**

---

## Project Overview

HiveMatrix is a **modular MSP platform** built on a monolithic service pattern. Each service is a self-contained Flask application that:
- Renders its own UI (server-side)
- Owns its own database
- Communicates via JWT tokens
- Is accessed through the Nexus proxy gateway

### Architecture Highlights

- **Nexus** (port 443): HTTPS gateway, handles auth, injects global CSS
- **Core** (port 5000): Authentication service, JWT minting, session management
- **Keycloak** (port 8080): Identity provider (OAuth2)
- **Services** (ports 5010+): Independent applications (Codex, Ledger, etc.)
- **Helm** (port 5004): Service orchestration, installation, configuration

---

## Essential Reading Order

1. **ARCHITECTURE.md** (ALL sections - this is mandatory)
2. **apps_registry.json** - Available services and their configurations
3. **master_config.json** - System-wide configuration
4. **services.json** - Service registry (auto-generated, don't edit manually)

---

## Key Architecture Rules

### 1. Authentication Flow (Section 3)

**Initial Login:**
- User → Nexus (443) → Keycloak OAuth2 login
- Keycloak redirects with authorization code
- Nexus exchanges code for Keycloak access token
- Nexus sends access token to Core
- Core validates with Keycloak, creates session, mints HiveMatrix JWT
- JWT includes session ID (jti) for revocation tracking
- Nexus stores JWT in Flask session cookie

**Session Management:**
- Sessions are **revokable** (stored in Core's session manager)
- Sessions expire after 1 hour
- On every request, Nexus validates JWT with Core
- Core checks: signature, expiration, and revocation status

**Logout Flow:**
- User clicks logout → Nexus calls Core's `/api/token/revoke`
- Core marks session as revoked (using jti from JWT)
- Nexus clears session cookie and browser storage
- Next request → session invalid → user must re-login

**Permission Levels:**
- `admin` - Full system access (members of `admins` group in Keycloak)
- `technician` - Technical operations (`technicians` group)
- `billing` - Financial operations (`billing` group)
- `client` - Limited access (default for users not in special groups)

**Critical for AJAX:**
- **ALL fetch calls MUST include `credentials: 'same-origin'`**
- Without it, session cookie isn't sent → auth fails → HTML error page instead of JSON

### 2. Service Communication (Section 4)

**Service-to-Service Calls:**
```python
from app.service_client import call_service

# Make API call to another service
response = call_service('codex', '/api/companies')
companies = response.json()
```

**How it works:**
1. Calling service requests service token from Core: `POST /service-token`
2. Core mints short-lived JWT (5 min) with `type: "service"`
3. `call_service()` automatically adds `Authorization: Bearer <token>`
4. Target service's `@token_required` decorator detects service call
5. Sets `g.is_service_call = True` and `g.service = "calling_service"`

**Service vs User Tokens:**
- Service calls bypass user permission checks
- Check `g.is_service_call` to distinguish in routes
- Service tokens expire in 5 minutes (vs 1 hour for users)

**Critical Rules:**
- **NEVER access another service's database directly**
- Always use service-to-service API calls
- Service tokens are trusted inter-service communication

### 3. Frontend & Styling (Section 5)

- **Services have NO CSS files** - Nexus injects `global.css`
- Use BEM classes from design system (Section 10)
- Templates are plain HTML with BEM classes
- Nexus injects side panel navigation automatically

**🚨 CRITICAL: CSS Reuse Policy**
- **ALWAYS check if a class exists before creating new CSS**
- **REUSE existing classes across all pages** - Don't create page-specific styles
- **Keep global.css small** - Every new class adds to file size for ALL pages
- Examples of reusable patterns:
  - Use `.status-text--success` for ANY green text (not just service status)
  - Use `.card` for ANY card-like container (not just specific pages)
  - Use utility classes (`.u-mb-2`, `.u-flex`) instead of custom spacing
- Before adding CSS, ask: "Does a similar class already exist?"
- When in doubt, use utility classes or modify existing components

### 4. URL Prefix Handling (Section 5)

```python
# ✅ CORRECT - Use werkzeug's ProxyFix
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# ❌ WRONG - Do NOT use custom PrefixMiddleware
```

Nexus strips the prefix before forwarding, so backends receive clean paths.

### 5. Configuration Management (Section 6)

- **DO NOT manually edit `.flaskenv`** - auto-generated by `config_manager.py`
- **DO NOT manually edit `services.json`** - auto-generated by `install_manager.py`
- Edit `apps_registry.json` and run `python install_manager.py update-config`
- Sync configs: `python config_manager.py sync-all`

### 6. Database (Section 11)

- Use `configparser.RawConfigParser()` (not `ConfigParser()`)
- Each service owns its database
- Connection strings in `instance/[service].conf`

### 7. Security (Section 10)

**Localhost Binding (CRITICAL):**
```python
# ✅ CORRECT - Backend services bind to localhost only
app.run(host='127.0.0.1', port=5040)

# ❌ WRONG - Exposes service directly to network
app.run(host='0.0.0.0', port=5040)
```

**Security Model:**
- Only Nexus (port 443) binds to `0.0.0.0` (external access)
- All backend services bind to `127.0.0.1` (localhost only)
- Keycloak, Core, Helm, and all apps MUST be localhost
- Services accessed externally via: `https://server:443/service-name/`
- Never accessed directly by port: `http://server:5010/` (blocked)

**Security Audit:**
```bash
python security_audit.py --audit          # Check port bindings
python security_audit.py --generate-firewall  # Generate UFW rules
sudo bash secure_firewall.sh              # Apply firewall
```

**Why this matters:**
- Prevents direct database access from internet
- Prevents bypassing authentication
- All requests go through Nexus → authenticated
- Firewall blocks ports 5000-5999, 8080 from external access

---

## Advanced Topics

### Database Best Practices (Section 11)

**Configuration:**
```python
# ✅ CORRECT - Use RawConfigParser for passwords with special chars
import configparser
config = configparser.RawConfigParser()
config.read('instance/myservice.conf')

# ❌ WRONG - ConfigParser breaks with % in passwords
config = configparser.ConfigParser()
```

**Model Patterns:**
- Each service owns its database (no cross-service database access)
- Use SQLAlchemy ORM
- String sizes: `String(50)` for IDs, `String(150)` for names, `Text` for long content
- Use `BigInteger` for large external IDs (Freshservice, Datto, etc.)
- Relationships: Use `back_populates` for bidirectional, `cascade="all, delete-orphan"` for cleanup

**Database Setup:**
- Create `init_db.py` for interactive setup
- Prompt for database credentials
- Test connection before saving
- Store in `instance/[service].conf` (auto-generated by config_manager)

### External System Integration (Section 12)

**Sync Script Pattern:**
```python
# pull_external_system.py
from app import app
from extensions import db
from models import Company, Contact
import requests

def sync_data():
    """Standalone sync script that imports Flask app"""
    with app.app_context():
        # API credentials from config
        api_key = app.config['MYSERVICE_CONFIG'].get('api', 'api_key')

        # Fetch from external API
        response = requests.get('https://api.example.com/data',
                               headers={'Authorization': f'Bearer {api_key}'})

        # Update database
        for item in response.json():
            record = Company.query.filter_by(external_id=item['id']).first()
            if not record:
                record = Company(external_id=item['id'])
                db.session.add(record)
            record.name = item['name']

        db.session.commit()

if __name__ == '__main__':
    sync_data()
```

**Key Points:**
- Standalone Python scripts (not Flask routes)
- Import Flask app and models directly
- Use `with app.app_context():` for database access
- Store API credentials in service's config file
- Can be run via cron for automated syncing
- Include logging and error handling

### Keycloak Auto-Configuration (Section 8)

**Automatic Setup:**
The `start.sh` script automatically configures Keycloak when:
1. Keycloak is freshly downloaded (directory didn't exist)
2. `client_secret` is missing from `master_config.json`
3. `master_config.json` is deleted (forces Keycloak reinstall)

**What Gets Created:**
- Realm: `hivematrix`
- Client: `core-client` with OAuth2 authorization code flow
- Admin user: `admin` / `admin` (change in production!)
- Groups: `admins`, `technicians`, `billing`, `client`
- Group mapper: OIDC mapper to include groups in JWT

**Configuration Sync:**
- Keycloak config saved to `master_config.json`
- All service `.flaskenv` files get Keycloak URLs from master config
- Two-way sync prevents configuration drift

**Manual Reconfiguration:**
```bash
# Force Keycloak reconfiguration
rm -rf ../keycloak-26.4.0
rm instance/configs/master_config.json
./start.sh
```

### Service Installation Requirements (Section 6)

**Required Files for Auto-Installation:**

**1. `install.sh`** - Must create:
```bash
python3 -m venv pyenv
pip install -r requirements.txt
mkdir -p instance
ln -sf ../hivematrix-helm/services.json services.json
```

**2. `requirements.txt`** - Minimum dependencies:
```
Flask==3.0.0
python-dotenv==1.0.0
PyJWT==2.8.0
cryptography==41.0.7
SQLAlchemy==2.0.23
psycopg2-binary==2.9.9
werkzeug==3.0.0
```

**3. Service Structure:**
```
hivematrix-myservice/
├── app/
│   ├── __init__.py          # ProxyFix, config loading
│   ├── auth.py              # @token_required, @admin_required
│   ├── routes.py            # Main routes
│   ├── service_client.py    # call_service() helper
│   └── templates/           # HTML with BEM classes only
├── instance/
│   └── myservice.conf       # DB config (auto-generated)
├── extensions.py            # db = SQLAlchemy()
├── models.py                # Database models
├── init_db.py              # Interactive DB setup
├── run.py                   # Entry point
├── install.sh              # Installation script
├── .flaskenv                # Auto-generated by config_manager
├── services.json            # Symlink to helm
└── requirements.txt
```

**4. Add to Registry:**
```json
// apps_registry.json
{
  "default_apps": {
    "myservice": {
      "name": "HiveMatrix MyService",
      "description": "Service description",
      "git_url": "https://github.com/user/hivematrix-myservice",
      "port": 5040,
      "required": false,
      "dependencies": ["core", "postgresql"],
      "install_order": 6
    }
  }
}
```

**5. Generate Config:**
```bash
python install_manager.py update-config
```

This auto-generates both `services.json` and `master_services.json`.

---

## Common Tasks

### Adding a New Service

1. **Read ARCHITECTURE.md Section 7** (AI Instructions for Building a New Service)
2. Copy `hivematrix-template` repository
3. Add to `apps_registry.json`
4. Run `python install_manager.py update-config`
5. Create `install.sh` script
6. Use `@token_required` decorator on all routes
7. **Use ProxyFix, NOT custom middleware**
8. **NO CSS files in the service**

### Fixing Authentication Issues

1. Check fetch calls include `credentials: 'same-origin'`
2. Verify `@token_required` decorator is used
3. Check ProxyFix is configured (not PrefixMiddleware)
4. Test with: `python create_test_token.py`

### Implementing Dark Mode

- Theme stored in Codex's `agents` table
- Nexus calls Codex API: `/api/public/user/theme?email=...`
- User can change via `/codex/settings` or sidebar toggle
- Agents must be synced from Keycloak first

### Debugging & Development Tools (Section 9)

**View Centralized Logs:**
```bash
cd hivematrix-helm
source pyenv/bin/activate

# View logs from specific service
python logs_cli.py codex --tail 50

# Filter by log level
python logs_cli.py core --level ERROR --tail 100

# View all services
python logs_cli.py --tail 30
```

**Generate Test JWT Tokens:**
```bash
# Generate admin token (24-hour expiration)
TOKEN=$(python create_test_token.py 2>/dev/null)

# Test authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:5010/codex/api/data

# Test endpoint with pretty JSON
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:5010/codex/api/data | jq
```

**Monitor Logs During Testing:**
```bash
# Terminal 1: Watch logs in real-time
watch -n 2 'python logs_cli.py myservice --tail 20'

# Terminal 2: Make test requests
TOKEN=$(python create_test_token.py 2>/dev/null)
curl -H "Authorization: Bearer $TOKEN" http://localhost:5010/api/test
```

**Debug Service Communication:**
```bash
# Test service-to-service call
TOKEN=$(python create_test_token.py 2>/dev/null)
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:5010/codex/api/companies
```

**Tools Available:**
- `logs_cli.py` - View centralized logs from Helm's PostgreSQL
- `create_test_token.py` - Generate valid JWT tokens for testing
- `test_with_token.sh` - Quick endpoint testing wrapper
- `security_audit.py` - Check service port bindings
- `config_manager.py` - Manage service configurations
- `install_manager.py` - Install and configure services

---

## File Structure Reference

```
hivematrix-[service]/
├── app/
│   ├── __init__.py          # Flask app, USE ProxyFix
│   ├── auth.py              # @token_required decorator (copy from template)
│   ├── routes.py            # Main routes
│   ├── service_client.py    # Service-to-service helper
│   └── templates/           # HTML only, NO CSS
├── instance/
│   └── [service].conf       # Database config (auto-generated)
├── .flaskenv                # Environment vars (auto-generated, don't edit)
├── requirements.txt         # Python dependencies
├── run.py                   # Entry point
├── init_db.py              # Interactive DB setup
├── install.sh              # Installation script
└── services.json           # Symlink to ../hivematrix-helm/services.json
```

---

## Critical Files (DO NOT EDIT MANUALLY)

❌ **Never manually edit:**
- `services.json` (except the master in helm)
- `master_services.json`
- `.flaskenv` files
- `instance/*.conf` files (unless debugging)

✅ **Edit these instead:**
- `apps_registry.json` → then run `update-config`
- `master_config.json` → then run `sync-all`

---

## Development Workflow

```bash
# Start entire platform
cd hivematrix-helm
./start.sh

# Or use CLI for individual services
source pyenv/bin/activate
python cli.py start codex
python cli.py status
python cli.py restart nexus

# Update configurations after changes
python config_manager.py sync-all
python install_manager.py update-config
```

---

## Common Mistakes to Avoid

1. ❌ Using custom `PrefixMiddleware` → ✅ Use `ProxyFix`
2. ❌ Adding CSS to service templates → ✅ Use BEM classes only
3. ❌ Creating new CSS without checking existing classes → ✅ **Reuse existing classes first!**
4. ❌ Editing `.flaskenv` manually → ✅ Edit `master_config.json`
5. ❌ Forgetting `credentials: 'same-origin'` → ✅ Add to all fetch calls
6. ❌ Accessing another service's DB → ✅ Use service-to-service API
7. ❌ Binding services to `0.0.0.0` → ✅ Bind to `127.0.0.1`
8. ❌ Skipping ARCHITECTURE.md → ✅ **Read it first!**

---

## When Things Break

### "JSON.parse: unexpected character at line 1"
- Missing `credentials: 'same-origin'` in fetch call
- Authentication failed, returned HTML instead of JSON
- Check browser console for 401/403 errors

### "Agent not found"
- User not synced from Keycloak to Codex
- Go to Codex → Agents → "🔄 Sync from Keycloak"

### Routes not working / 404 errors
- Using PrefixMiddleware instead of ProxyFix
- Check `app/__init__.py` for middleware configuration

### Dark mode not saving
- Agent not synced from Keycloak
- Missing `credentials: 'same-origin'`
- Check `/api/my/settings` endpoint exists

### Service not starting
- Check `python cli.py status`
- View logs: `python logs_cli.py [service] --tail 50`
- Verify `.flaskenv` exists and has correct values

---

## Testing Checklist

Before committing changes:

- [ ] Read relevant ARCHITECTURE.md sections
- [ ] Services use ProxyFix (not custom middleware)
- [ ] All routes have `@token_required` decorator
- [ ] Fetch calls include `credentials: 'same-origin'`
- [ ] No CSS files in service (BEM classes only)
- [ ] Configuration files auto-generated (not manually edited)
- [ ] Security audit passes: `python security_audit.py --audit`
- [ ] Services bind to localhost (not 0.0.0.0)
- [ ] Tested with real JWT token

---

## Resources

- **Architecture**: `ARCHITECTURE.md` (READ THIS FIRST!)
- **Service Template**: `https://github.com/ruapotato/hivematrix-template`
- **Apps Registry**: `apps_registry.json`
- **Debugging Tools**: `logs_cli.py`, `create_test_token.py`, `security_audit.py`
- **Configuration**: `config_manager.py`, `install_manager.py`

---

## Questions to Ask Before Coding

1. Have I read ARCHITECTURE.md completely?
2. Which section of ARCHITECTURE.md covers this task?
3. Am I using ProxyFix or custom middleware? (Use ProxyFix!)
4. Am I adding CSS to a service? (Don't! Use BEM classes)
5. **Before creating new CSS, does a similar class already exist?** (Check global.css!)
6. **Can I use utility classes instead?** (`.u-mb-2`, `.u-text-center`, etc.)
7. Am I editing auto-generated files? (Stop! Edit the source instead)
8. Do my fetch calls have `credentials: 'same-origin'`?
9. Are my routes protected with `@token_required`?
10. Am I accessing another service's database? (Use API instead)
11. Are services binding to localhost (not 0.0.0.0)?
12. Am I using RawConfigParser (not ConfigParser)?

---

## Quick Code Snippets

### Protected Route with Permission Check
```python
@app.route('/admin/settings')
@admin_required
def admin_settings():
    # Only admins can access
    return render_template('admin/settings.html', user=g.user)
```

### API Route for Both Users and Services
```python
@app.route('/api/data')
@token_required
def api_data():
    if g.is_service_call:
        # Service-to-service call
        return jsonify({'data': get_data()})
    else:
        # User call - check permission
        if g.user.get('permission_level') != 'admin':
            return {'error': 'Admin only'}, 403
        return jsonify({'data': get_data()})
```

### AJAX Request with Credentials
```javascript
// Fetch data from API
fetch('/codex/api/companies', {
    credentials: 'same-origin'  // REQUIRED!
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error('Error:', err));

// POST data
fetch('/codex/api/companies', {
    method: 'POST',
    credentials: 'same-origin',  // REQUIRED!
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: 'New Company'})
})
.then(res => res.json())
.then(data => console.log(data));
```

### Service-to-Service Call
```python
from app.service_client import call_service

# Get companies from Codex
response = call_service('codex', '/api/companies')
if response.status_code == 200:
    companies = response.json()
```

### Database Config with RawConfigParser
```python
import configparser
import os

config_path = os.path.join(app.instance_path, 'myservice.conf')
config = configparser.RawConfigParser()  # Use RawConfigParser!
config.read(config_path)

# Read database connection
app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database', 'connection_string',
    fallback=f"sqlite:///{os.path.join(app.instance_path, 'myservice.db')}")
```

### ProxyFix Middleware Setup
```python
# In app/__init__.py
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # Trust X-Forwarded-For
    x_proto=1,    # Trust X-Forwarded-Proto
    x_host=1,     # Trust X-Forwarded-Host
    x_prefix=1    # Trust X-Forwarded-Prefix (for url_for)
)
```

### Logging to Helm
```python
from app import helm_logger

@app.route('/api/action')
@token_required
def do_action():
    try:
        helm_logger.info("Action started", extra={'user': g.user.get('username')})
        result = perform_action()
        helm_logger.info(f"Action completed: {result}")
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        helm_logger.error(f"Action failed: {e}", exc_info=True)
        return {'error': 'Internal error'}, 500
```

---

## Final Reminder

**🚨 ARCHITECTURE.md is the law. When in doubt, read it again. 🚨**

The architecture document has been carefully designed to keep the codebase simple and maintainable for AI assistants. Following it ensures the system works correctly and remains easy to modify.

**Good luck, and remember: ARCHITECTURE.md first, code second!**
