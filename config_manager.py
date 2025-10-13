#!/usr/bin/env python3
"""
HiveMatrix Helm - Centralized Configuration Manager
Manages all configuration for all HiveMatrix applications
"""

import os
import json
import configparser
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """
    Centralized configuration manager for all HiveMatrix apps
    All apps should get their configuration from Helm
    """

    def __init__(self, helm_dir: str = None):
        self.helm_dir = Path(helm_dir) if helm_dir else Path(__file__).parent
        self.parent_dir = self.helm_dir.parent
        self.config_dir = self.helm_dir / "instance" / "configs"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Master configuration file
        self.master_config_file = self.config_dir / "master_config.json"
        self.load_master_config()

    def load_master_config(self):
        """Load master configuration"""
        # Default configuration
        defaults = {
            "system": {
                "environment": "development",
                "log_level": "INFO",
                "secret_key": os.urandom(24).hex(),
                "hostname": "localhost"
            },
            "keycloak": {
                "url": "http://localhost:8080",
                "realm": "hivematrix",
                "client_id": "core-client",
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
            "apps": {}
        }

        if self.master_config_file.exists():
            with open(self.master_config_file, 'r') as f:
                loaded_config = json.load(f)

            # Merge loaded config with defaults (loaded values take precedence)
            self.master_config = defaults.copy()
            for key in loaded_config:
                if isinstance(loaded_config[key], dict) and key in self.master_config:
                    self.master_config[key].update(loaded_config[key])
                else:
                    self.master_config[key] = loaded_config[key]
        else:
            self.master_config = defaults
            self.save_master_config()

    def save_master_config(self):
        """Save master configuration"""
        with open(self.master_config_file, 'w') as f:
            json.dump(self.master_config, f, indent=2)

    def get_app_config(self, app_name: str) -> Dict[str, Any]:
        """Get configuration for a specific app"""
        if app_name not in self.master_config['apps']:
            self.master_config['apps'][app_name] = {}

        config = {
            "system": self.master_config['system'].copy(),
            "keycloak": self.master_config['keycloak'].copy(),
            "app": self.master_config['apps'][app_name].copy()
        }

        # Add database info if the app needs it
        if 'database' in self.master_config['apps'][app_name]:
            db_type = self.master_config['apps'][app_name]['database']
            if db_type in self.master_config['databases']:
                config['database'] = self.master_config['databases'][db_type].copy()

        return config

    def set_app_config(self, app_name: str, config: Dict[str, Any]):
        """Set configuration for a specific app"""
        self.master_config['apps'][app_name] = config
        self.save_master_config()

    def update_app_config(self, app_name: str, updates: Dict[str, Any]):
        """Update specific values in an app's configuration"""
        if app_name not in self.master_config['apps']:
            self.master_config['apps'][app_name] = {}

        self.master_config['apps'][app_name].update(updates)
        self.save_master_config()

    def generate_app_dotenv(self, app_name: str) -> str:
        """Generate .flaskenv content for an app"""
        config = self.get_app_config(app_name)

        # Determine hostname and if it's an IP address
        hostname = config['system'].get('hostname', 'localhost')
        is_ip_address = hostname.replace('.', '').isdigit()

        # For Core, always use direct Keycloak connection (backend URL)
        # Core needs to connect to Keycloak directly for OAuth metadata
        if app_name == 'core':
            keycloak_server_url = f"{config['keycloak']['url']}/realms/{config['keycloak']['realm']}"
        else:
            # For other services (like Nexus), use proxied URL based on hostname
            if hostname == 'localhost':
                keycloak_server_url = config['keycloak']['url']
            elif is_ip_address:
                keycloak_server_url = f"https://{hostname}/keycloak"
            else:
                keycloak_server_url = f"https://{hostname}/keycloak"

        lines = [
            f"FLASK_APP=run.py",
            f"FLASK_ENV={config['system']['environment']}",
            f"SECRET_KEY={config['system']['secret_key']}",
            f"SERVICE_NAME={app_name}",
            f"",
            f"# Keycloak Configuration",
            f"KEYCLOAK_SERVER_URL={keycloak_server_url}",
            f"KEYCLOAK_BACKEND_URL={config['keycloak']['url']}",
            f"KEYCLOAK_REALM={config['keycloak']['realm']}",
            f"KEYCLOAK_CLIENT_ID={config['keycloak']['client_id']}",
        ]

        # Add client secret if present
        if 'client_secret' in config['keycloak']:
            lines.append(f"KEYCLOAK_CLIENT_SECRET='{config['keycloak']['client_secret']}'")

        # Add JWT configuration for Core
        if app_name == 'core':
            lines.extend([
                f"",
                f"# JWT Configuration",
                f"JWT_PRIVATE_KEY_FILE=keys/jwt_private.pem",
                f"JWT_PUBLIC_KEY_FILE=keys/jwt_public.pem",
                f"JWT_ISSUER=hivematrix-core",
                f"JWT_ALGORITHM=RS256",
            ])

        # Add database configuration if present (PostgreSQL only, not Neo4j)
        if 'database' in config and 'host' in config['database']:
            lines.extend([
                f"",
                f"# Database Configuration",
                f"DB_HOST={config['database']['host']}",
                f"DB_PORT={config['database']['port']}",
            ])

            # Add app-specific database name if configured
            if 'db_name' in config['app']:
                lines.append(f"DB_NAME={config['app']['db_name']}")

        # Add service URLs
        if hostname == 'localhost':
            nexus_url = "http://localhost:8000"
        elif is_ip_address:
            # For IP addresses, use HTTPS on port 443 (Nexus with SSL)
            nexus_url = f"https://{hostname}"
        else:
            # For domain names, use HTTPS
            nexus_url = f"https://{hostname}"

        lines.extend([
            f"",
            f"# Service URLs",
            f"CORE_SERVICE_URL=http://localhost:5000",
            f"NEXUS_SERVICE_URL={nexus_url}",
            f"HELM_SERVICE_URL=http://localhost:5004",
        ])

        # Add app-specific environment variables from config sections
        if 'sections' in config['app']:
            # For KnowledgeTree, add Neo4j and Codex configuration
            if app_name == 'knowledgetree':
                if 'database' in config['app']['sections']:
                    db_config = config['app']['sections']['database']
                    lines.extend([
                        f"",
                        f"# Neo4j Configuration",
                        f"NEO4J_URI={db_config.get('neo4j_uri', 'bolt://localhost:7687')}",
                        f"NEO4J_USER={db_config.get('neo4j_user', 'neo4j')}",
                        f"NEO4J_PASSWORD={db_config.get('neo4j_password', '')}",
                    ])
                if 'services' in config['app']['sections']:
                    svc_config = config['app']['sections']['services']
                    lines.extend([
                        f"",
                        f"# Service Integration",
                        f"CODEX_SERVICE_URL={svc_config.get('codex_url', 'http://localhost:5010')}",
                    ])

        return "\n".join(lines) + "\n"

    def write_app_dotenv(self, app_name: str):
        """Write .flaskenv file for an app"""
        app_dir = self.parent_dir / f"hivematrix-{app_name}"
        if not app_dir.exists():
            raise FileNotFoundError(f"App directory not found: {app_dir}")

        dotenv_path = app_dir / ".flaskenv"
        content = self.generate_app_dotenv(app_name)

        with open(dotenv_path, 'w') as f:
            f.write(content)

    def generate_app_conf(self, app_name: str) -> str:
        """Generate instance/app.conf content for an app"""
        config = self.get_app_config(app_name)
        conf = configparser.ConfigParser()

        # Database section if present
        if 'database' in config:
            conf['database'] = {}
            db = config['database']
            app_db = config['app'].get('db_name', f'{app_name}_db')
            app_user = config['app'].get('db_user', f'{app_name}_user')

            conf['database']['connection_string'] = (
                f"postgresql://{app_user}:password@{db['host']}:{db['port']}/{app_db}"
            )
            conf['database']['db_host'] = db['host']
            conf['database']['db_port'] = str(db['port'])
            conf['database']['db_name'] = app_db
            conf['database']['db_user'] = app_user

        # App-specific sections
        if 'sections' in config['app']:
            for section_name, section_data in config['app']['sections'].items():
                conf[section_name] = section_data

        # Write to string
        from io import StringIO
        output = StringIO()
        conf.write(output)
        return output.getvalue()

    def write_app_conf(self, app_name: str):
        """Write instance/app.conf file for an app"""
        app_dir = self.parent_dir / f"hivematrix-{app_name}"
        if not app_dir.exists():
            raise FileNotFoundError(f"App directory not found: {app_dir}")

        instance_dir = app_dir / "instance"
        instance_dir.mkdir(exist_ok=True)

        conf_path = instance_dir / f"{app_name}.conf"
        content = self.generate_app_conf(app_name)

        with open(conf_path, 'w') as f:
            f.write(content)

    def sync_all_apps(self):
        """Sync configuration to all installed apps"""
        from install_manager import InstallManager

        install_mgr = InstallManager(str(self.helm_dir))
        installed_apps = install_mgr.get_installed_apps()

        for app_name in installed_apps:
            try:
                self.write_app_dotenv(app_name)
                self.write_app_conf(app_name)
                print(f"✓ Synced configuration for {app_name}")
            except Exception as e:
                print(f"✗ Failed to sync {app_name}: {e}")

    def setup_app_database(self, app_name: str, db_name: str = None, db_user: str = None, db_password: str = None):
        """Setup PostgreSQL database for an app"""
        import subprocess

        if not db_name:
            db_name = f"{app_name}_db"
        if not db_user:
            db_user = f"{app_name}_user"
        if not db_password:
            db_password = os.urandom(16).hex()

        # Create database and user
        commands = [
            f"CREATE DATABASE {db_name};",
            f"CREATE USER {db_user} WITH PASSWORD '{db_password}';",
            f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};",
        ]

        try:
            for cmd in commands:
                subprocess.run(
                    ['sudo', '-u', 'postgres', 'psql', '-c', cmd],
                    check=True,
                    capture_output=True
                )

            # Update app config
            self.update_app_config(app_name, {
                'database': 'postgresql',
                'db_name': db_name,
                'db_user': db_user,
                'db_password': db_password
            })

            return True, f"Database {db_name} created successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to create database: {e.stderr.decode()}"


def main():
    import sys

    manager = ConfigManager()

    if len(sys.argv) < 2:
        print("Usage: config_manager.py <command> [args]")
        print("Commands:")
        print("  get <app>           - Get app configuration")
        print("  set <app> <json>    - Set app configuration")
        print("  gen-dotenv <app>    - Generate .flaskenv for app")
        print("  gen-conf <app>      - Generate instance conf for app")
        print("  write-dotenv <app>  - Write .flaskenv to app directory")
        print("  write-conf <app>    - Write instance conf to app directory")
        print("  sync-all            - Sync config to all apps")
        print("  setup-db <app>      - Setup database for app")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'get' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        config = manager.get_app_config(app_name)
        print(json.dumps(config, indent=2))

    elif command == 'set' and len(sys.argv) >= 4:
        app_name = sys.argv[2]
        config = json.loads(sys.argv[3])
        manager.set_app_config(app_name, config)
        print(f"Configuration updated for {app_name}")

    elif command == 'gen-dotenv' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        print(manager.generate_app_dotenv(app_name))

    elif command == 'gen-conf' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        print(manager.generate_app_conf(app_name))

    elif command == 'write-dotenv' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        manager.write_app_dotenv(app_name)
        print(f"Written .flaskenv for {app_name}")

    elif command == 'write-conf' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        manager.write_app_conf(app_name)
        print(f"Written instance conf for {app_name}")

    elif command == 'sync-all':
        manager.sync_all_apps()

    elif command == 'setup-db' and len(sys.argv) >= 3:
        app_name = sys.argv[2]
        success, message = manager.setup_app_database(app_name)
        print(message)
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
