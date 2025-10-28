from flask import Flask
import json
import os
from dotenv import load_dotenv

# Load environment variables from .flaskenv
load_dotenv('.flaskenv')

app = Flask(__name__, instance_relative_config=True)

# --- Explicitly load all required configuration from environment variables ---
app.config['CORE_SERVICE_URL'] = os.environ.get('CORE_SERVICE_URL', 'http://localhost:5000')
app.config['SERVICE_NAME'] = os.environ.get('SERVICE_NAME', 'helm')

# Helm can run without Core - authentication will be disabled for UI but service management works
if not app.config['CORE_SERVICE_URL']:
    print("WARNING: CORE_SERVICE_URL not set. Authentication will be disabled.")
    print("Service management will still work, but admin dashboard authentication will not.")

# Load database connection from config file
import configparser
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

config_path = os.path.join(app.instance_path, 'helm.conf')
config = configparser.RawConfigParser()
config.read(config_path)
app.config['HELM_CONFIG'] = config

# Database configuration - PostgreSQL only
db_connection = config.get('database', 'connection_string', fallback=None)

if not db_connection:
    # If no database configured, use a dummy URI
    # init_db.py will configure it properly
    print("WARNING: Database not configured. Using temporary configuration.")
    print("Please complete the setup by running: python init_db.py")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/postgres'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_connection

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Load services configuration for service discovery and management
try:
    with open('services.json') as f:
        services_config = json.load(f)
        app.config['SERVICES'] = services_config
except FileNotFoundError:
    print("WARNING: services.json not found. Service management will not work.")
    app.config['SERVICES'] = {}

from extensions import db
db.init_app(app)

# Apply middleware to handle URL prefix when behind Nexus proxy
from app.middleware import PrefixMiddleware
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=f'/{app.config["SERVICE_NAME"]}')

# Import routes
from app import routes
from app import api_routes
from app import app_manager_routes

# Start log file watcher in background thread
import threading
from pathlib import Path

def start_log_watcher_thread():
    """Start the log watcher in a background thread"""
    from log_watcher import start_log_watcher
    watcher_thread = threading.Thread(target=start_log_watcher, daemon=True)
    watcher_thread.start()

# Only start log watcher if logs directory exists (i.e., not during initial setup)
logs_dir = Path('logs')
if logs_dir.exists():
    start_log_watcher_thread()

# Add custom Jinja2 filters
from datetime import datetime

@app.template_filter('format_uptime')
def format_uptime(timestamp_str):
    """Convert ISO timestamp to human-readable uptime"""
    if not timestamp_str:
        return '-'

    try:
        # Parse ISO format timestamp
        if isinstance(timestamp_str, str):
            started_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            started_at = timestamp_str

        # Calculate uptime
        now = datetime.utcnow()
        delta = now - started_at.replace(tzinfo=None)

        # Format based on duration
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours}h"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            if hours > 0:
                return f"{days}d {hours}h"
            return f"{days}d"
    except Exception as e:
        return '-'
