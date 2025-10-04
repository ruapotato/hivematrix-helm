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
