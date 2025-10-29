#!/usr/bin/env python3
"""
HiveMatrix Backup Tool

Backs up all PostgreSQL databases, Neo4j databases, and Keycloak directory.
Creates a timestamped zip file with all data.

Usage:
    sudo python3 backup.py                    # Backup to /tmp
    sudo python3 backup.py /path/to/output    # Backup to specific directory
    python3 backup.py --dry-run               # Test without creating backup

Default output: /tmp/hivematrix_backup_YYYYMMDD_HHMMSS.zip
Output file is owned by the user who ran sudo (not root)

Requires:
    - Root/sudo access (REQUIRED for reliable backups)
    - When run with sudo, uses 'sudo -u postgres' for database dumps (no passwords needed)
    - pg_dump, pg_dumpall for PostgreSQL
    - neo4j-admin for Neo4j (or direct data directory copy)
"""

import os
import sys
import json
import shutil
import subprocess
import configparser
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile

SCRIPT_DIR = Path(__file__).parent.absolute()
MASTER_CONFIG = SCRIPT_DIR / "instance" / "configs" / "master_config.json"
SERVICES_CONFIG = SCRIPT_DIR / "services.json"


class HiveMatrixBackup:
    def __init__(self, output_dir=None):
        """Initialize backup with configuration."""
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Default to /tmp for output
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("/tmp")

        # Don't create output_dir if it doesn't exist (let it fail if /tmp doesn't exist)
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.backup_name = f"hivematrix_backup_{self.timestamp}"
        self.backup_zip = self.output_dir / f"{self.backup_name}.zip"
        self.temp_dir = None
        self.original_user = None
        self.original_group = None

        # Store original user info if running as root
        if os.geteuid() == 0:
            # Get the user who ran sudo
            sudo_user = os.environ.get('SUDO_USER')
            if sudo_user:
                import pwd
                import grp
                user_info = pwd.getpwnam(sudo_user)
                self.original_user = user_info.pw_uid
                self.original_group = user_info.pw_gid

        # Load configurations
        self.load_config()

    def load_config(self):
        """Load master configuration and service definitions."""
        if not MASTER_CONFIG.exists():
            print(f"ERROR: Master config not found: {MASTER_CONFIG}")
            sys.exit(1)

        with open(MASTER_CONFIG) as f:
            self.master_config = json.load(f)

        if not SERVICES_CONFIG.exists():
            print(f"ERROR: Services config not found: {SERVICES_CONFIG}")
            sys.exit(1)

        with open(SERVICES_CONFIG) as f:
            self.services = json.load(f)

        # Extract database configs
        self.pg_config = self.master_config.get("databases", {}).get("postgresql", {})
        self.neo4j_config = self.master_config.get("databases", {}).get("neo4j", {})

    def create_temp_dir(self):
        """Create temporary directory for backup files."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="hivematrix_backup_"))
        # Make temp directory world-writable so postgres user can write to it
        os.chmod(self.temp_dir, 0o777)
        print(f"Created temp directory: {self.temp_dir}")

    def cleanup_temp_dir(self):
        """Remove temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"Cleaned up temp directory")

    def backup_postgresql_databases(self):
        """Backup all PostgreSQL databases used by HiveMatrix services."""
        print("\n=== Backing up PostgreSQL databases ===")
        pg_backup_dir = self.temp_dir / "postgresql"
        pg_backup_dir.mkdir(parents=True, exist_ok=True)
        # Make directory writable for postgres user
        os.chmod(pg_backup_dir, 0o777)

        # Get list of databases from service configurations
        databases = set()

        # Scan all service config files for PostgreSQL databases
        # Store database info including credentials
        db_info = {}  # {db_name: {'user': ..., 'password': ...}}

        for service_name, service_info in self.services.items():
            if service_name == "keycloak":
                continue

            # Resolve service path properly
            svc_path = service_info.get("path", "")
            if svc_path.startswith("../"):
                service_path = (SCRIPT_DIR / svc_path).resolve()
            elif svc_path == ".":
                service_path = SCRIPT_DIR
            else:
                service_path = Path(svc_path).resolve()

            config_file = service_path / "instance" / f"{service_name}.conf"

            if config_file.exists():
                config = configparser.RawConfigParser()  # Use RawConfigParser to handle special chars like %
                try:
                    config.read(config_file)
                    if config.has_option("database", "db_name"):
                        db_name = config.get("database", "db_name")

                        # Extract credentials from connection string
                        if config.has_option("database", "connection_string"):
                            conn_str = config.get("database", "connection_string")
                            # Parse postgresql://user:password@host:port/dbname
                            import re
                            match = re.match(r'postgresql://([^:]+):([^@]+)@', conn_str)
                            if match:
                                db_user = match.group(1)
                                db_password = match.group(2)
                                # URL decode the password if needed
                                from urllib.parse import unquote
                                db_password = unquote(db_password)
                                db_info[db_name] = {
                                    'user': db_user,
                                    'password': db_password
                                }

                        databases.add(db_name)
                        print(f"  Found database: {db_name} (from {service_name})")
                except Exception as e:
                    print(f"  Warning: Could not read config for {service_name}: {e}")

        if not databases:
            print("  No PostgreSQL databases found")
            return

        # Backup each database
        pg_host = self.pg_config.get("host", "localhost")
        pg_port = self.pg_config.get("port", 5432)

        for db_name in databases:
            print(f"  Backing up database: {db_name}")
            dump_file = pg_backup_dir / f"{db_name}.sql"

            try:
                # If running as root, use sudo -u postgres for peer authentication
                # This bypasses all password issues
                if os.geteuid() == 0:
                    cmd = [
                        "sudo", "-u", "postgres",
                        "pg_dump",
                        "-F", "p",  # Plain text format
                        "-f", str(dump_file),
                        db_name
                    ]
                else:
                    # Not root - try with user credentials from config
                    db_creds = db_info.get(db_name, {})
                    pg_user = db_creds.get('user', self.pg_config.get("admin_user", "postgres"))
                    pg_password = db_creds.get('password', '')

                    cmd = [
                        "pg_dump",
                        "-h", pg_host,
                        "-p", str(pg_port),
                        "-U", pg_user,
                        "-F", "p",  # Plain text format
                        "-f", str(dump_file),
                        db_name
                    ]

                    env = os.environ.copy()
                    if pg_password:
                        env['PGPASSWORD'] = pg_password

                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"    ✓ Backed up {db_name} ({dump_file.stat().st_size} bytes)")
            except subprocess.CalledProcessError as e:
                print(f"    ✗ Failed to backup {db_name}: {e.stderr}")

        # Also backup global objects (roles, tablespaces)
        print("  Backing up PostgreSQL global objects (roles, tablespaces)")
        globals_file = pg_backup_dir / "globals.sql"

        # For globals, use sudo -u postgres to run as postgres user with peer auth
        admin_user = self.pg_config.get("admin_user", "postgres")

        try:
            # If running as root, use sudo -u postgres for peer authentication
            if os.geteuid() == 0:
                cmd = [
                    "sudo", "-u", admin_user,
                    "pg_dumpall",
                    "-g",  # Globals only
                    "-f", str(globals_file)
                ]
            else:
                # Not running as root - skip globals (would need password)
                print(f"    ⊘ Skipping globals (not running as root)")
                return

            env = os.environ.copy()
            subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
            print(f"    ✓ Backed up global objects ({globals_file.stat().st_size} bytes)")
        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed to backup globals: {e.stderr}")

    def backup_neo4j_databases(self):
        """Backup Neo4j databases using neo4j-admin dump."""
        print("\n=== Backing up Neo4j databases ===")
        neo4j_backup_dir = self.temp_dir / "neo4j"
        neo4j_backup_dir.mkdir(parents=True, exist_ok=True)

        # Check if Neo4j is used by any service
        neo4j_used = False
        for service_name, service_info in self.services.items():
            # Resolve service path properly
            svc_path = service_info.get("path", "")
            if svc_path.startswith("../"):
                service_path = (SCRIPT_DIR / svc_path).resolve()
            elif svc_path == ".":
                service_path = SCRIPT_DIR
            else:
                service_path = Path(svc_path).resolve()

            config_file = service_path / "instance" / f"{service_name}.conf"

            if config_file.exists():
                config = configparser.RawConfigParser()  # Use RawConfigParser to handle special chars
                try:
                    config.read(config_file)
                    if config.has_option("database", "neo4j_uri"):
                        neo4j_used = True
                        print(f"  Found Neo4j usage in {service_name}")
                except:
                    pass

        if not neo4j_used:
            print("  No Neo4j databases found")
            return

        # Check if Neo4j is running and stop it
        neo4j_was_running = False
        try:
            result = subprocess.run(["sudo", "systemctl", "is-active", "neo4j"],
                                  capture_output=True, text=True)
            if result.stdout.strip() == "active":
                neo4j_was_running = True
                print("  Stopping Neo4j for backup...")
                subprocess.run(["sudo", "systemctl", "stop", "neo4j"], check=True)
                print("    ✓ Neo4j stopped")
                # Wait a moment for Neo4j to fully stop
                import time
                time.sleep(2)
        except Exception as e:
            print(f"    ⚠ Could not check/stop Neo4j service: {e}")

        try:
            # Use neo4j-admin dump for proper backup
            print("  Using neo4j-admin database dump...")

            # Set permissions on backup directory so neo4j user can write
            os.chmod(neo4j_backup_dir, 0o777)

            # Dump the default database (usually "neo4j")
            databases = ["neo4j"]  # Default database name

            for db_name in databases:
                dump_file = neo4j_backup_dir / f"{db_name}.dump"
                print(f"  Backing up database: {db_name}")

                try:
                    # Use sudo to run as root, then neo4j-admin dump
                    cmd = [
                        "sudo",
                        "neo4j-admin",
                        "database",
                        "dump",
                        db_name,
                        "--to-path=" + str(neo4j_backup_dir),
                        "--overwrite-destination=true"
                    ]

                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    print(f"    ✓ Backed up {db_name} ({dump_file.stat().st_size} bytes)")
                except subprocess.CalledProcessError as e:
                    print(f"    ✗ Failed to backup {db_name}: {e.stderr}")
                except Exception as e:
                    print(f"    ✗ Error during backup: {e}")
        finally:
            # Fix Neo4j data directory permissions (neo4j-admin creates files as root)
            print("  Fixing Neo4j permissions...")
            try:
                subprocess.run(["sudo", "chown", "-R", "neo4j:neo4j", "/var/lib/neo4j/data/databases/neo4j"], check=True)
                subprocess.run(["sudo", "chown", "-R", "neo4j:neo4j", "/var/lib/neo4j/data/transactions/neo4j"], check=True)
                print("    ✓ Fixed Neo4j permissions")
            except Exception as e:
                print(f"    ⚠ Failed to fix Neo4j permissions: {e}")
                print(f"    You may need to run manually:")
                print(f"      sudo chown -R neo4j:neo4j /var/lib/neo4j/data/databases/neo4j")
                print(f"      sudo chown -R neo4j:neo4j /var/lib/neo4j/data/transactions/neo4j")

            # Restart Neo4j if it was running before
            if neo4j_was_running:
                print("  Restarting Neo4j...")
                try:
                    subprocess.run(["sudo", "systemctl", "start", "neo4j"], check=True)
                    print("    ✓ Neo4j restarted")
                except Exception as e:
                    print(f"    ✗ Failed to restart Neo4j: {e}")
                    print(f"    Please restart manually: sudo systemctl start neo4j")

    def backup_keycloak(self):
        """Backup Keycloak directory."""
        print("\n=== Backing up Keycloak ===")
        keycloak_backup_dir = self.temp_dir / "keycloak"
        keycloak_backup_dir.mkdir(parents=True, exist_ok=True)

        # Get Keycloak path from services config
        keycloak_info = self.services.get("keycloak", {})
        keycloak_path = keycloak_info.get("path", "../keycloak-26.4.0")

        # Resolve the path properly from SCRIPT_DIR
        if keycloak_path.startswith("../"):
            keycloak_dir = (SCRIPT_DIR / keycloak_path).resolve()
        else:
            keycloak_dir = Path(keycloak_path).resolve()

        if not keycloak_dir.exists():
            print(f"  ✗ Keycloak directory not found: {keycloak_dir}")
            return

        print(f"  Found Keycloak directory: {keycloak_dir}")
        print(f"  Backing up entire Keycloak directory...")

        # Use tar to preserve permissions, ownership, and symlinks perfectly
        # This is more reliable than shutil.copytree for system files
        keycloak_tar = keycloak_backup_dir / "keycloak.tar.gz"

        try:
            # Create tar archive with full preservation
            cmd = [
                "tar",
                "--exclude=*.log",  # Exclude log files - must come before source
                "--exclude=log",    # Exclude log directory
                "--exclude=tmp",    # Exclude tmp directory
                "-czf", str(keycloak_tar),
                "-C", str(keycloak_dir.parent),  # Change to parent dir
                keycloak_dir.name   # Archive just the keycloak directory
            ]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)

            tar_size_mb = keycloak_tar.stat().st_size / (1024 * 1024)
            print(f"    ✓ Backed up complete Keycloak installation ({tar_size_mb:.2f} MB)")

        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed to backup Keycloak with tar: {e.stderr}")
            # Fallback to shutil.copytree
            print(f"  Falling back to directory copy method...")
            try:
                def ignore_patterns(dir, files):
                    """Ignore log files and temp directories."""
                    ignore = []
                    for f in files:
                        if f.endswith('.log') or f == 'tmp' or f == 'log':
                            ignore.append(f)
                    return ignore

                # Remove tar file if it was partially created
                if keycloak_tar.exists():
                    keycloak_tar.unlink()

                shutil.copytree(keycloak_dir, keycloak_backup_dir / "keycloak",
                              ignore=ignore_patterns, dirs_exist_ok=True)
                print(f"    ✓ Backed up Keycloak using directory copy")
            except Exception as e2:
                print(f"    ✗ Failed to backup Keycloak: {e2}")
        except Exception as e:
            print(f"    ✗ Unexpected error backing up Keycloak: {e}")

    def backup_configs(self):
        """Backup HiveMatrix configuration files."""
        print("\n=== Backing up configurations ===")
        config_backup_dir = self.temp_dir / "configs"
        config_backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup master config
        if MASTER_CONFIG.exists():
            shutil.copy2(MASTER_CONFIG, config_backup_dir / "master_config.json")
            print(f"  ✓ Backed up master_config.json")

        # Note: services.json and master_services.json are auto-generated by Helm
        # from apps_registry.json, so we don't back them up. They will be regenerated
        # after restore using: python install_manager.py update-config
        print(f"  Note: Skipping auto-generated files (services.json, master_services.json)")

        # Backup apps_registry.json which is the source of truth
        apps_registry = SCRIPT_DIR / "apps_registry.json"
        if apps_registry.exists():
            shutil.copy2(apps_registry, config_backup_dir / "apps_registry.json")
            print(f"  ✓ Backed up apps_registry.json")

        # Backup Core JWT keys if they exist
        core_keys_dir = (SCRIPT_DIR / ".." / "hivematrix-core" / "keys").resolve()
        if core_keys_dir.exists():
            dest_keys_dir = config_backup_dir / "core_keys"
            shutil.copytree(core_keys_dir, dest_keys_dir, dirs_exist_ok=True)
            print(f"  ✓ Backed up Core JWT keys")

    def create_backup_archive(self):
        """Create final zip archive."""
        print(f"\n=== Creating backup archive ===")
        print(f"  Archive: {self.backup_zip}")

        with zipfile.ZipFile(self.backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.temp_dir)
                    zipf.write(file_path, arcname)

        # Change ownership to original user if running as root
        if self.original_user is not None and self.original_group is not None:
            os.chown(self.backup_zip, self.original_user, self.original_group)
            print(f"  Changed ownership to {os.environ.get('SUDO_USER')}")

        size_mb = self.backup_zip.stat().st_size / (1024 * 1024)
        print(f"  ✓ Backup created: {self.backup_zip} ({size_mb:.2f} MB)")

    def run(self):
        """Execute full backup process."""
        print("=" * 60)
        print("HiveMatrix Backup Tool")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"Output: {self.backup_zip}")
        if self.original_user is not None:
            sudo_user = os.environ.get('SUDO_USER', 'unknown')
            print(f"File will be owned by: {sudo_user}")
        print()

        # Check if running as root/sudo
        if os.geteuid() != 0:
            print("WARNING: Not running as root. Database backups may fail.")
            print("Recommendation: Run with sudo for complete backup")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Backup cancelled")
                sys.exit(0)

        try:
            self.create_temp_dir()
            self.backup_configs()
            self.backup_postgresql_databases()
            self.backup_neo4j_databases()
            self.backup_keycloak()
            self.create_backup_archive()

            print("\n" + "=" * 60)
            print("✓ Backup completed successfully!")
            print("=" * 60)
            print(f"Backup file: {self.backup_zip}")
            print()

        except KeyboardInterrupt:
            print("\n\nBackup cancelled by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n\n✗ Backup failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            self.cleanup_temp_dir()


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Backup HiveMatrix databases and configs")
    parser.add_argument("output_dir", nargs="?", help="Output directory for backup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be backed up without creating backup")
    args = parser.parse_args()

    backup = HiveMatrixBackup(args.output_dir)

    if args.dry_run:
        print("DRY RUN MODE - No backup will be created")
        print()
        backup.load_config()
        # Just show what would be backed up
        backup.create_temp_dir()
        try:
            backup.backup_configs()
            backup.backup_postgresql_databases()
            backup.backup_neo4j_databases()
            backup.backup_keycloak()
        finally:
            backup.cleanup_temp_dir()
    else:
        backup.run()


if __name__ == "__main__":
    main()
