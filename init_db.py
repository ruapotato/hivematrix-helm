#!/usr/bin/env python3
"""
Helm Database Initialization - Fully Automated
Automatically creates database, user, and schema
"""

import os
import sys
import subprocess
import configparser
from pathlib import Path

def run_command(cmd, description=None, capture=True):
    """Run a shell command and return success status"""
    if description:
        print(f"  {description}...")
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return True, result.stdout
        else:
            subprocess.run(cmd, shell=True, check=True)
            return True, ""
    except subprocess.CalledProcessError as e:
        if capture:
            return False, e.stderr
        else:
            return False, str(e)

def setup_postgresql():
    """Ensure PostgreSQL is installed and running"""
    print("\n✓ PostgreSQL check...")

    # Check if PostgreSQL is installed
    success, _ = run_command("which psql", capture=True)
    if not success:
        print("  PostgreSQL not found. Installing...")
        run_command("sudo apt update", "Updating package list", capture=False)
        run_command(
            "sudo apt install -y postgresql postgresql-contrib libpq-dev python3-dev",
            "Installing PostgreSQL",
            capture=False
        )

    # Ensure PostgreSQL is running
    run_command("sudo systemctl start postgresql 2>/dev/null || true")
    run_command("sudo systemctl enable postgresql 2>/dev/null || true")
    print("  ✓ PostgreSQL ready")

def create_database():
    """Create Helm database and user"""
    print("\n✓ Setting up Helm database...")

    db_name = "helm_db"
    db_user = "helm_user"
    db_password = os.urandom(24).hex()[:24]

    # Check if database exists
    success, output = run_command(
        f"sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='{db_name}'\""
    )

    if "1" not in output:
        print("  Creating database and user...")

        # Create database and user in single psql call
        create_sql = f"""
CREATE DATABASE {db_name};
CREATE USER {db_user} WITH PASSWORD '{db_password}';
GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};
"""
        # Use heredoc to handle quotes properly
        run_command(f"sudo -u postgres psql <<'EOF'\n{create_sql}\nEOF\n")

        # Grant schema permissions (PostgreSQL 15+)
        schema_sql = f"""
GRANT ALL ON SCHEMA public TO {db_user};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {db_user};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {db_user};
"""
        run_command(f"sudo -u postgres psql -d {db_name} <<'EOF'\n{schema_sql}\nEOF\n")

        print(f"  ✓ Database created: {db_name}")
        print(f"  ✓ User created: {db_user}")
    else:
        print(f"  ✓ Database {db_name} already exists")
        # Try to get existing password from config
        instance_dir = Path(__file__).parent / "instance"
        config_file = instance_dir / "helm.conf"
        password_found = False

        if config_file.exists():
            config = configparser.ConfigParser()
            config.read(config_file)
            try:
                conn_str = config.get('database', 'connection_string')
                # Extract password from connection string
                import re
                match = re.search(r':([^@]+)@', conn_str)
                if match:
                    db_password = match.group(1)
                    print(f"  ✓ Using existing password from config")
                    password_found = True
            except:
                pass

        # If we couldn't get the password from config, update PostgreSQL with new password
        if not password_found:
            print("  ✓ Config not found, updating database password...")
            update_sql = f"ALTER USER {db_user} WITH PASSWORD '{db_password}';"
            run_command(f"sudo -u postgres psql <<'EOF'\n{update_sql}\nEOF\n")
            print(f"  ✓ Database password updated")

    return db_name, db_user, db_password

def save_config(db_name, db_user, db_password):
    """Save database configuration"""
    instance_dir = Path(__file__).parent / "instance"
    instance_dir.mkdir(exist_ok=True)

    config_file = instance_dir / "helm.conf"

    config = configparser.ConfigParser()
    config['database'] = {
        'connection_string': f'postgresql://{db_user}:{db_password}@localhost:5432/{db_name}',
        'db_host': 'localhost',
        'db_port': '5432',
        'db_name': db_name,
        'db_user': db_user
    }

    with open(config_file, 'w') as f:
        config.write(f)

    print(f"\n✓ Configuration saved to instance/helm.conf")
    return config_file

def initialize_schema(db_name, db_user, db_password):
    """Initialize database schema"""
    print("\n✓ Initializing database schema...")

    # Try SQL file first
    schema_file = Path(__file__).parent / "schema.sql"
    if schema_file.exists():
        success, output = run_command(
            f"PGPASSWORD='{db_password}' psql -h localhost -U {db_user} -d {db_name} -f {schema_file}"
        )
        if success:
            print("  ✓ Schema initialized from schema.sql")
            return

    # Fallback to Python ORM
    print("  Using Python ORM to create tables...")
    try:
        # Import after config is saved
        from app import app
        from extensions import db

        with app.app_context():
            db.create_all()
            print("  ✓ Schema initialized")
            print("    - log_entries")
            print("    - service_status")
            print("    - service_metrics")
    except Exception as e:
        print(f"  ⚠ Schema initialization warning: {e}")
        print("  (This is normal if tables already exist)")

def main():
    print("="*60)
    print("  Helm Database Setup (Automated)")
    print("="*60)

    # 1. Setup PostgreSQL
    setup_postgresql()

    # 2. Create database and user
    db_name, db_user, db_password = create_database()

    # 3. Save configuration
    save_config(db_name, db_user, db_password)

    # 4. Initialize schema
    initialize_schema(db_name, db_user, db_password)

    print("\n" + "="*60)
    print("  ✓ Helm database setup complete!")
    print("="*60)
    print()

if __name__ == '__main__':
    main()
