#!/usr/bin/env python3
"""
HiveMatrix Restore Tool

Restores PostgreSQL databases, Neo4j databases, and Keycloak directory from a backup.

Usage:
    sudo python3 restore.py <backup_zip_file> [options]

Options:
    --postgresql-only    Restore only PostgreSQL databases
    --neo4j-only        Restore only Neo4j databases
    --keycloak-only     Restore only Keycloak directory
    --configs-only      Restore only configuration files
    --force             Skip confirmation prompts (dangerous!)

Requires:
    - Root/sudo access for database restoration
    - psql, createdb for PostgreSQL
    - Neo4j must be stopped before restoration

WARNING: This will OVERWRITE existing data! Make sure you have a backup of current data.
"""

import os
import sys
import json
import shutil
import subprocess
import configparser
from pathlib import Path
import tempfile
import zipfile
import argparse

SCRIPT_DIR = Path(__file__).parent.absolute()


class HiveMatrixRestore:
    def __init__(self, backup_zip, options):
        """Initialize restore with backup file."""
        self.backup_zip = Path(backup_zip)
        self.options = options
        self.temp_dir = None

        if not self.backup_zip.exists():
            print(f"ERROR: Backup file not found: {self.backup_zip}")
            sys.exit(1)

        # Determine what to restore
        self.restore_all = not any([
            options.postgresql_only,
            options.neo4j_only,
            options.keycloak_only,
            options.configs_only
        ])

    def extract_backup(self):
        """Extract backup zip to temporary directory."""
        print(f"\n=== Extracting backup ===")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="hivematrix_restore_"))
        print(f"Extracting to: {self.temp_dir}")

        with zipfile.ZipFile(self.backup_zip, 'r') as zipf:
            zipf.extractall(self.temp_dir)

        # Make temp directory and contents readable by postgres user
        os.chmod(self.temp_dir, 0o755)

        # Make all extracted files readable
        for root, dirs, files in os.walk(self.temp_dir):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)

        print(f"✓ Extracted backup")

    def cleanup_temp_dir(self):
        """Remove temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"Cleaned up temp directory")

    def restore_configs(self):
        """Restore configuration files."""
        print("\n=== Restoring configurations ===")
        config_dir = self.temp_dir / "configs"

        if not config_dir.exists():
            print("  No configuration backup found")
            return

        # Restore master config
        master_config_src = config_dir / "master_config.json"
        master_config_dest = SCRIPT_DIR / "instance" / "configs" / "master_config.json"

        if master_config_src.exists():
            master_config_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(master_config_src, master_config_dest)
            print(f"  ✓ Restored master_config.json")

        # Note: services.json and master_services.json are auto-generated
        print(f"  Note: Skipping auto-generated files (will be regenerated)")

        # Restore apps_registry.json if it exists
        apps_registry_src = config_dir / "apps_registry.json"
        apps_registry_dest = SCRIPT_DIR / "apps_registry.json"

        if apps_registry_src.exists():
            shutil.copy2(apps_registry_src, apps_registry_dest)
            print(f"  ✓ Restored apps_registry.json")

        # Restore Core JWT keys
        core_keys_src = config_dir / "core_keys"
        core_keys_dest = (SCRIPT_DIR / ".." / "hivematrix-core" / "keys").resolve()

        if core_keys_src.exists():
            core_keys_dest.parent.mkdir(parents=True, exist_ok=True)
            if core_keys_dest.exists():
                shutil.rmtree(core_keys_dest)
            shutil.copytree(core_keys_src, core_keys_dest)
            print(f"  ✓ Restored Core JWT keys")

        # Restore service config files
        service_configs_src = config_dir / "service_configs"
        if service_configs_src.exists():
            # Load services.json to find where to restore each config
            services_file = SCRIPT_DIR / "services.json"
            if services_file.exists():
                with open(services_file) as f:
                    services = json.load(f)

                restored_count = 0
                for config_file in service_configs_src.glob("*.conf"):
                    service_name = config_file.stem  # e.g., "helm" from "helm.conf"

                    if service_name in services:
                        service_info = services[service_name]
                        svc_path = service_info.get("path", "")

                        # Resolve service path
                        if svc_path.startswith("../"):
                            service_path = (SCRIPT_DIR / svc_path).resolve()
                        elif svc_path == ".":
                            service_path = SCRIPT_DIR
                        else:
                            service_path = Path(svc_path).resolve()

                        dest_dir = service_path / "instance"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = dest_dir / config_file.name

                        shutil.copy2(config_file, dest_file)
                        restored_count += 1

                if restored_count > 0:
                    print(f"  ✓ Restored {restored_count} service config files")

        # Remind user to regenerate auto-generated files
        print(f"\n  → After restore, regenerate service configs with:")
        print(f"     cd {SCRIPT_DIR}")
        print(f"     source pyenv/bin/activate")
        print(f"     python install_manager.py update-config")

    def restore_postgresql_databases(self):
        """Restore PostgreSQL databases."""
        print("\n=== Restoring PostgreSQL databases ===")
        pg_backup_dir = self.temp_dir / "postgresql"

        if not pg_backup_dir.exists():
            print("  No PostgreSQL backup found")
            return

        # Get PostgreSQL connection info from master config
        master_config_file = SCRIPT_DIR / "instance" / "configs" / "master_config.json"
        if not master_config_file.exists():
            print("  ERROR: Master config not found. Restore configs first.")
            return

        with open(master_config_file) as f:
            master_config = json.load(f)

        pg_config = master_config.get("databases", {}).get("postgresql", {})
        pg_host = pg_config.get("host", "localhost")
        pg_port = pg_config.get("port", 5432)
        pg_user = pg_config.get("admin_user", "postgres")

        # Restore database credentials from service configs
        credentials_file = pg_backup_dir / "db_credentials.json"
        if credentials_file.exists():
            print("  Restoring PostgreSQL database users from backed-up credentials")
            try:
                with open(credentials_file) as f:
                    db_credentials = json.load(f)

                for db_name, creds in db_credentials.items():
                    username = creds.get('user')
                    password = creds.get('password')

                    if not username or not password:
                        continue

                    try:
                        # Create or update the user with the password
                        # Using DO block to create if not exists, then set password
                        sql = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{username}') THEN
        CREATE ROLE {username} WITH LOGIN;
    END IF;
END
$$;
ALTER ROLE {username} WITH PASSWORD '{password}';
"""
                        # Write to temp file to avoid shell escaping issues
                        temp_sql = self.temp_dir / f"restore_user_{username}.sql"
                        with open(temp_sql, 'w') as f:
                            f.write(sql)
                        os.chmod(temp_sql, 0o644)

                        # Execute SQL
                        if os.geteuid() == 0:
                            cmd = ["sudo", "-u", "postgres", "psql", "-f", str(temp_sql)]
                        else:
                            cmd = ["psql", "-h", pg_host, "-p", str(pg_port), "-U", pg_user, "-f", str(temp_sql)]

                        subprocess.run(cmd, check=True, capture_output=True, text=True)
                        temp_sql.unlink()

                        print(f"    ✓ Restored user {username} for database {db_name}")
                    except subprocess.CalledProcessError as e:
                        print(f"    Warning: Could not restore user {username}: {e.stderr[:200]}")
                    except Exception as e:
                        print(f"    Warning: Error restoring user {username}: {e}")

                print(f"    ✓ Restored {len(db_credentials)} database users")
            except Exception as e:
                print(f"    Warning: Error restoring database credentials: {e}")
        else:
            print("  No database credentials found in backup")

        # Restore each database
        for sql_file in pg_backup_dir.glob("*.sql"):
            if sql_file.name == "globals.sql":
                continue

            db_name = sql_file.stem
            print(f"  Restoring database: {db_name}")

            # Drop existing database if it exists
            try:
                if os.geteuid() == 0:
                    cmd = ["sudo", "-u", "postgres", "dropdb", "--if-exists", db_name]
                else:
                    cmd = ["dropdb", "-h", pg_host, "-p", str(pg_port), "-U", pg_user, "--if-exists", db_name]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"    Dropped existing database {db_name}")
            except subprocess.CalledProcessError as e:
                print(f"    Note: Could not drop database (may not exist): {e.stderr[:200]}")

            # Create new database
            try:
                if os.geteuid() == 0:
                    cmd = ["sudo", "-u", "postgres", "createdb", db_name]
                else:
                    cmd = ["createdb", "-h", pg_host, "-p", str(pg_port), "-U", pg_user, db_name]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"    Created database {db_name}")
            except subprocess.CalledProcessError as e:
                print(f"    ✗ Failed to create database: {e.stderr}")
                continue

            # Restore database from dump
            try:
                if os.geteuid() == 0:
                    cmd = ["sudo", "-u", "postgres", "psql", "-d", db_name, "-f", str(sql_file)]
                else:
                    cmd = ["psql", "-h", pg_host, "-p", str(pg_port), "-U", pg_user, "-d", db_name, "-f", str(sql_file)]

                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"    ✓ Restored database {db_name}")
            except subprocess.CalledProcessError as e:
                print(f"    ✗ Failed to restore database: {e.stderr[:500]}")

    def restore_neo4j_databases(self):
        """Restore Neo4j databases using neo4j-admin load."""
        print("\n=== Restoring Neo4j databases ===")
        neo4j_backup_dir = self.temp_dir / "neo4j"

        if not neo4j_backup_dir.exists():
            print("  No Neo4j backup found")
            return

        print("  WARNING: This will OVERWRITE your existing Neo4j data!")

        if not self.options.force:
            response = input("  Continue with Neo4j restoration? (yes/no): ")
            if response.lower() != 'yes':
                print("  Skipped Neo4j restoration")
                return

        # Find dump files
        dump_files = list(neo4j_backup_dir.glob("*.dump"))
        if not dump_files:
            print("  ✗ No Neo4j dump files found in backup")
            return

        # Check if Neo4j is running and stop it
        neo4j_was_running = False
        try:
            result = subprocess.run(["sudo", "systemctl", "is-active", "neo4j"],
                                  capture_output=True, text=True)
            if result.stdout.strip() == "active":
                neo4j_was_running = True
                print("  Stopping Neo4j for restore...")
                subprocess.run(["sudo", "systemctl", "stop", "neo4j"], check=True)
                print("    ✓ Neo4j stopped")
                # Wait a moment for Neo4j to fully stop
                import time
                time.sleep(2)
        except Exception as e:
            print(f"    ⚠ Could not check/stop Neo4j service: {e}")

        try:
            # Restore each database
            for dump_file in dump_files:
                db_name = dump_file.stem  # Get database name from filename (e.g., "neo4j" from "neo4j.dump")
                print(f"  Restoring database: {db_name}")

                try:
                    # Use sudo neo4j-admin database load to restore
                    cmd = [
                        "sudo",
                        "neo4j-admin",
                        "database",
                        "load",
                        db_name,
                        "--from-path=" + str(neo4j_backup_dir),
                        "--overwrite-destination=true"
                    ]

                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    print(f"    ✓ Restored database {db_name}")
                except subprocess.CalledProcessError as e:
                    print(f"    ✗ Failed to restore {db_name}: {e.stderr}")
                except Exception as e:
                    print(f"    ✗ Error during restore: {e}")
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
                    # Wait a few seconds for Neo4j to fully start
                    import time
                    print("    Waiting for Neo4j to start...")
                    time.sleep(5)
                    print("    ✓ Neo4j should be ready")
                except Exception as e:
                    print(f"    ✗ Failed to restart Neo4j: {e}")
                    print(f"    Please restart manually: sudo systemctl start neo4j")

    def restore_keycloak(self):
        """Restore Keycloak directory."""
        print("\n=== Restoring Keycloak ===")
        keycloak_backup_dir = self.temp_dir / "keycloak"

        if not keycloak_backup_dir.exists():
            print("  No Keycloak backup found")
            return

        # Check if we have a tar archive or directory backup
        keycloak_tar = keycloak_backup_dir / "keycloak.tar.gz"
        keycloak_full_backup = keycloak_backup_dir / "keycloak"
        has_tar_backup = keycloak_tar.exists()
        has_dir_backup = keycloak_full_backup.exists()

        # Load services config to find Keycloak path
        services_config = SCRIPT_DIR / "services.json"
        if not services_config.exists():
            print("  ERROR: services.json not found. Restore configs first.")
            return

        with open(services_config) as f:
            services = json.load(f)

        keycloak_info = services.get("keycloak", {})
        keycloak_path = keycloak_info.get("path", "../keycloak-26.4.0")

        # Resolve the path properly from SCRIPT_DIR
        if keycloak_path.startswith("../"):
            keycloak_dir = (SCRIPT_DIR / keycloak_path).resolve()
        else:
            keycloak_dir = Path(keycloak_path).resolve()

        print(f"  Restoring to: {keycloak_dir}")

        if has_tar_backup:
            # Restore from tar archive (preserves permissions perfectly)
            print(f"  Restoring from Keycloak tar archive...")

            # Backup existing Keycloak directory
            if keycloak_dir.exists():
                backup_name = f"keycloak_backup_{int(os.times().elapsed * 1000)}"
                backup_path = keycloak_dir.parent / backup_name
                print(f"  Backing up existing Keycloak to {backup_name}")
                shutil.move(str(keycloak_dir), str(backup_path))

            try:
                # Extract tar archive
                cmd = [
                    "tar",
                    "-xzf", str(keycloak_tar),
                    "-C", str(keycloak_dir.parent)
                ]

                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"    ✓ Extracted Keycloak from tar archive")

                # Change ownership to user who ran sudo
                if os.geteuid() == 0:
                    sudo_user = os.environ.get('SUDO_USER')
                    if sudo_user:
                        print(f"  Fixing Keycloak ownership...")
                        try:
                            import pwd
                            user_info = pwd.getpwnam(sudo_user)
                            user_uid = user_info.pw_uid
                            user_gid = user_info.pw_gid

                            # Use chown command for speed
                            chown_cmd = ["chown", "-R", f"{user_uid}:{user_gid}", str(keycloak_dir)]
                            subprocess.run(chown_cmd, check=True, capture_output=True)
                            print(f"    ✓ Changed ownership to {sudo_user}")
                        except Exception as e:
                            print(f"    Warning: Could not change ownership: {e}")

                # Fix executable permissions on Keycloak scripts
                print(f"  Fixing Keycloak script permissions...")
                try:
                    bin_dir = keycloak_dir / "bin"
                    if bin_dir.exists():
                        chmod_cmd = ["chmod", "+x"] + [str(f) for f in bin_dir.glob("*.sh")]
                        if len(chmod_cmd) > 2:  # Has .sh files
                            subprocess.run(chmod_cmd, check=True, capture_output=True)
                            print(f"    ✓ Made scripts executable")
                except Exception as e:
                    print(f"    Warning: Could not fix permissions: {e}")

                print(f"    ✓ Restored complete Keycloak installation")

            except subprocess.CalledProcessError as e:
                print(f"    ✗ Failed to extract Keycloak: {e.stderr}")
            except Exception as e:
                print(f"    ✗ Failed to restore Keycloak: {e}")

        elif has_dir_backup:
            # Restore entire Keycloak directory
            print(f"  Restoring complete Keycloak installation...")

            # Backup existing Keycloak directory
            if keycloak_dir.exists():
                backup_name = f"keycloak_backup_{int(os.times().elapsed * 1000)}"
                backup_path = keycloak_dir.parent / backup_name
                print(f"  Backing up existing Keycloak to {backup_name}")
                shutil.move(str(keycloak_dir), str(backup_path))

            try:
                # Copy the entire Keycloak directory
                shutil.copytree(keycloak_full_backup, keycloak_dir, dirs_exist_ok=True)
                print(f"    ✓ Restored complete Keycloak installation")

                # Fix ownership to the user who ran sudo (not root)
                if os.geteuid() == 0:
                    sudo_user = os.environ.get('SUDO_USER')
                    if sudo_user:
                        print(f"  Fixing Keycloak ownership...")
                        try:
                            import pwd
                            user_info = pwd.getpwnam(sudo_user)
                            user_uid = user_info.pw_uid
                            user_gid = user_info.pw_gid

                            # Recursively change ownership
                            for root, dirs, files in os.walk(keycloak_dir):
                                os.chown(root, user_uid, user_gid)
                                for d in dirs:
                                    os.chown(os.path.join(root, d), user_uid, user_gid)
                                for f in files:
                                    os.chown(os.path.join(root, f), user_uid, user_gid)

                            print(f"    ✓ Changed ownership to {sudo_user}")
                        except Exception as e:
                            print(f"    Warning: Could not change ownership: {e}")
                            print(f"    Run manually: sudo chown -R {sudo_user}:{sudo_user} {keycloak_dir}")

                # Fix executable permissions on Keycloak scripts
                print(f"  Fixing Keycloak script permissions...")
                try:
                    bin_dir = keycloak_dir / "bin"
                    if bin_dir.exists():
                        chmod_cmd = ["chmod", "+x"] + [str(f) for f in bin_dir.glob("*.sh")]
                        if len(chmod_cmd) > 2:  # Has .sh files
                            subprocess.run(chmod_cmd, check=True, capture_output=True)
                            print(f"    ✓ Made scripts executable")
                except Exception as e:
                    print(f"    Warning: Could not fix permissions: {e}")

            except Exception as e:
                print(f"    ✗ Failed to restore Keycloak: {e}")
        else:
            # Legacy backup format - restore only data/ and conf/
            print(f"  Restoring Keycloak data and conf (legacy backup)...")

            if not keycloak_dir.exists():
                print(f"  ERROR: Keycloak directory not found: {keycloak_dir}")
                print(f"  Cannot restore data/conf to non-existent Keycloak installation")
                return

            for dir_name in ["data", "conf"]:
                src_dir = keycloak_backup_dir / dir_name
                if src_dir.exists():
                    dest_dir = keycloak_dir / dir_name
                    print(f"  Restoring {dir_name}/ ...")

                    # Backup existing directory
                    if dest_dir.exists():
                        backup_name = f"{dir_name}_backup_{int(os.times().elapsed * 1000)}"
                        backup_path = keycloak_dir / backup_name
                        shutil.move(str(dest_dir), str(backup_path))
                        print(f"    Backed up existing {dir_name}/ to {backup_name}")

                    try:
                        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                        print(f"    ✓ Restored {dir_name}/")
                    except Exception as e:
                        print(f"    ✗ Failed to restore {dir_name}/: {e}")

    def verify_backup_contents(self):
        """Display what's in the backup."""
        print("\n=== Backup Contents ===")

        contents = {
            "configs": (self.temp_dir / "configs").exists(),
            "postgresql": (self.temp_dir / "postgresql").exists(),
            "neo4j": (self.temp_dir / "neo4j").exists(),
            "keycloak": (self.temp_dir / "keycloak").exists()
        }

        for item, exists in contents.items():
            status = "✓" if exists else "✗"
            print(f"  {status} {item}")

        if not any(contents.values()):
            print("\n  ERROR: Backup appears to be empty or invalid")
            sys.exit(1)

    def update_hostname_if_changed(self):
        """Check if hostname changed and automatically reconfigure Keycloak."""
        print("\n=== Checking hostname ===")

        master_config_file = SCRIPT_DIR / "instance" / "configs" / "master_config.json"
        if not master_config_file.exists():
            print("  No master config found")
            return

        try:
            # Get current hostname
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
            current_ip = result.stdout.strip().split()[0] if result.stdout.strip() else None

            if not current_ip:
                print("  Could not detect current IP address")
                return

            # Read master config
            with open(master_config_file) as f:
                config = json.load(f)

            old_hostname = config.get("system", {}).get("hostname", "")

            if old_hostname and old_hostname != current_ip:
                print(f"  Hostname changed: {old_hostname} → {current_ip}")

                # Update hostname in config
                if "system" not in config:
                    config["system"] = {}
                config["system"]["hostname"] = current_ip

                with open(master_config_file, 'w') as f:
                    json.dump(config, f, indent=2)

                print(f"  ✓ Updated master_config.json with new hostname")

                # Automatically run Keycloak configuration
                print(f"\n=== Reconfiguring Keycloak for new hostname ===")
                configure_script = SCRIPT_DIR / "configure_keycloak.sh"
                if configure_script.exists():
                    try:
                        # Run configure_keycloak.sh with the new IP
                        env = os.environ.copy()
                        env['KEYCLOAK_HOSTNAME'] = current_ip

                        result = subprocess.run(
                            ["bash", str(configure_script)],
                            cwd=str(SCRIPT_DIR),
                            env=env,
                            capture_output=False,  # Show output to user
                            text=True
                        )

                        if result.returncode == 0:
                            print(f"  ✓ Keycloak reconfigured successfully")
                        else:
                            print(f"  ✗ Keycloak reconfiguration failed")
                            print(f"  Please run manually: ./configure_keycloak.sh")
                    except Exception as e:
                        print(f"  Warning: Could not run configure_keycloak.sh: {e}")
                        print(f"  Please run manually: ./configure_keycloak.sh")
                else:
                    print(f"  Warning: configure_keycloak.sh not found")
                    print(f"  Please run manually if needed")
            else:
                print(f"  Hostname unchanged: {current_ip}")

        except Exception as e:
            print(f"  Warning: Could not check/update hostname: {e}")

    def run(self):
        """Execute restore process."""
        print("=" * 60)
        print("HiveMatrix Restore Tool")
        print("=" * 60)
        print(f"Backup file: {self.backup_zip}")
        print()

        # Check if running as root/sudo
        if os.geteuid() != 0:
            print("WARNING: Not running as root. Database restoration may fail.")
            print("Recommendation: Run with sudo for complete restoration")

            if not self.options.force:
                response = input("Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    print("Restore cancelled")
                    sys.exit(0)

        # Final warning
        if not self.options.force:
            print("\n" + "!" * 60)
            print("WARNING: This will OVERWRITE existing data!")
            print("!" * 60)
            response = input("\nAre you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled")
                sys.exit(0)

        try:
            self.extract_backup()
            self.verify_backup_contents()

            if self.restore_all or self.options.configs_only:
                self.restore_configs()

            if self.restore_all or self.options.postgresql_only:
                self.restore_postgresql_databases()

            if self.restore_all or self.options.neo4j_only:
                self.restore_neo4j_databases()

            if self.restore_all or self.options.keycloak_only:
                self.restore_keycloak()

            # Check if hostname changed and update master_config.json
            self.update_hostname_if_changed()

            print("\n" + "=" * 60)
            print("✓ Restore completed!")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Start services:")
            print("     ./start.sh")
            print()
            print("  2. Verify data integrity and test login")
            print()
            print("Note: If hostname changed, Keycloak was automatically reconfigured.")
            print("      Services will need to be restarted to pick up new credentials.")
            print()

        except KeyboardInterrupt:
            print("\n\nRestore cancelled by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n\n✗ Restore failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            self.cleanup_temp_dir()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Restore HiveMatrix from backup",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "backup_zip",
        help="Path to backup zip file"
    )

    parser.add_argument(
        "--postgresql-only",
        action="store_true",
        help="Restore only PostgreSQL databases"
    )

    parser.add_argument(
        "--neo4j-only",
        action="store_true",
        help="Restore only Neo4j databases"
    )

    parser.add_argument(
        "--keycloak-only",
        action="store_true",
        help="Restore only Keycloak directory"
    )

    parser.add_argument(
        "--configs-only",
        action="store_true",
        help="Restore only configuration files"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts (dangerous!)"
    )

    args = parser.parse_args()

    restore = HiveMatrixRestore(args.backup_zip, args)
    restore.run()


if __name__ == "__main__":
    main()
