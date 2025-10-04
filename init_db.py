"""
Interactive database initialization script for HiveMatrix Helm
"""

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
from models import LogEntry, ServiceStatus, ServiceMetric

def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("\n--- PostgreSQL Database Configuration ---")

    # Load existing or use defaults
    db_details = {
        'host': config.get('database_credentials', 'db_host', fallback='localhost'),
        'port': config.get('database_credentials', 'db_port', fallback='5432'),
        'user': config.get('database_credentials', 'db_user', fallback='helm_user'),
        'dbname': config.get('database_credentials', 'db_dbname', fallback='helm_db')
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
    config_path = os.path.join(instance_path, 'helm.conf')

    config = configparser.RawConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)
        print(f"\n✓ Existing configuration found: {config_path}")
    else:
        print(f"\n→ Creating new config: {config_path}")
        os.makedirs(instance_path, exist_ok=True)

    # Database configuration - PostgreSQL only
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  Helm requires a PostgreSQL database for production use   ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\nMake sure you have:")
    print("  1. PostgreSQL installed and running")
    print("  2. Created a database (e.g., helm_db)")
    print("  3. Created a user with access to that database")
    print("\nSee SETUP.md for Ubuntu installation instructions.\n")

    # PostgreSQL configuration
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

    # Reload the app with the new database configuration
    print("\nReloading application with new database configuration...")

    # We need to reinitialize the app to pick up the new config
    from importlib import reload
    import sys

    # Remove the app module from cache to force reload
    if 'app' in sys.modules:
        del sys.modules['app']

    # Re-import with new configuration
    from app import app as new_app
    from extensions import db as new_db

    # Initialize database schema
    with new_app.app_context():
        print("Initializing database schema...")
        new_db.create_all()
        print("✓ Database schema initialized successfully!")
        print("\nCreated tables:")
        print("  - log_entries (immutable log storage)")
        print("  - service_status (service health tracking)")
        print("  - service_metrics (performance metrics)")
        print("\n✅ Helm database setup complete!")
        print("You can now start Helm with: python run.py")

if __name__ == '__main__':
    init_db()
