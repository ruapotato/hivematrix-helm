#!/usr/bin/env python3
"""
HiveMatrix Helm - Installation Manager
Handles app installation, dependency management, and configuration
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class InstallManager:
    def __init__(self, helm_dir: str = None):
        self.helm_dir = Path(helm_dir) if helm_dir else Path(__file__).parent
        self.parent_dir = self.helm_dir.parent
        self.apps_registry_file = self.helm_dir / "apps_registry.json"
        self.services_json = self.helm_dir / "services.json"
        self.master_services_json = self.helm_dir / "master_services.json"

        # Load registry
        with open(self.apps_registry_file, 'r') as f:
            self.registry = json.load(f)

    def check_system_dependencies(self) -> Dict[str, bool]:
        """Check which system dependencies are installed"""
        results = {}

        # Check PostgreSQL
        try:
            subprocess.run(['psql', '--version'],
                          capture_output=True, check=True)
            results['postgresql'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            results['postgresql'] = False

        # Check Python
        try:
            result = subprocess.run([sys.executable, '--version'],
                                   capture_output=True, check=True, text=True)
            version = result.stdout.strip()
            results['python'] = '3.8' in version or '3.9' in version or '3.1' in version
        except:
            results['python'] = False

        # Check Git
        try:
            subprocess.run(['git', '--version'],
                          capture_output=True, check=True)
            results['git'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            results['git'] = False

        # Check Java (for Keycloak)
        try:
            result = subprocess.run(['java', '-version'],
                                   capture_output=True, check=True, text=True, stderr=subprocess.STDOUT)
            results['java'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            results['java'] = False

        # Check Keycloak
        keycloak_path = self.parent_dir / "keycloak-26.0.5"
        results['keycloak'] = keycloak_path.exists()

        # Check Neo4j
        try:
            subprocess.run(['neo4j', 'version'],
                          capture_output=True, check=True)
            results['neo4j'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            results['neo4j'] = False

        return results

    def install_system_dependency(self, dep_name: str) -> Tuple[bool, str]:
        """Install a system dependency"""
        dep_info = self.registry['system_dependencies'].get(dep_name)
        if not dep_info:
            return False, f"Unknown dependency: {dep_name}"

        if dep_name == 'postgresql':
            return self._install_postgresql()
        elif dep_name == 'keycloak':
            return self._install_keycloak()
        elif dep_name == 'neo4j':
            return self._install_neo4j()
        else:
            return False, f"No installer for {dep_name}"

    def _install_postgresql(self) -> Tuple[bool, str]:
        """Install PostgreSQL"""
        try:
            print("Installing PostgreSQL...")
            subprocess.run([
                'sudo', 'apt', 'update'
            ], check=True)
            subprocess.run([
                'sudo', 'apt', 'install', '-y',
                'postgresql', 'postgresql-contrib',
                'python3-dev', 'libpq-dev'
            ], check=True)
            subprocess.run([
                'sudo', 'systemctl', 'start', 'postgresql'
            ], check=True)
            subprocess.run([
                'sudo', 'systemctl', 'enable', 'postgresql'
            ], check=True)
            return True, "PostgreSQL installed successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install PostgreSQL: {e}"

    def _install_keycloak(self) -> Tuple[bool, str]:
        """Download and setup Keycloak"""
        try:
            keycloak_dir = self.parent_dir / "keycloak-26.0.5"
            if keycloak_dir.exists():
                return True, "Keycloak already installed"

            print("Downloading Keycloak 26.0.5...")
            tar_file = self.parent_dir / "keycloak-26.0.5.tar.gz"

            subprocess.run([
                'wget', '-O', str(tar_file),
                'https://github.com/keycloak/keycloak/releases/download/26.0.5/keycloak-26.0.5.tar.gz'
            ], check=True)

            print("Extracting Keycloak...")
            subprocess.run([
                'tar', '-xzf', str(tar_file), '-C', str(self.parent_dir)
            ], check=True)

            tar_file.unlink()

            return True, "Keycloak installed successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install Keycloak: {e}"

    def _install_neo4j(self) -> Tuple[bool, str]:
        """Install Neo4j"""
        try:
            print("Installing Neo4j...")
            # Add Neo4j repository
            subprocess.run([
                'wget', '-O', '-', 'https://debian.neo4j.com/neotechnology.gpg.key'
            ], stdout=subprocess.PIPE, check=True)

            # Install Neo4j
            subprocess.run([
                'sudo', 'apt', 'install', '-y', 'neo4j'
            ], check=True)

            return True, "Neo4j installed successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install Neo4j: {e}"

    def clone_app(self, app_key: str) -> Tuple[bool, str]:
        """Clone an app from git"""
        # Check in both core_apps and default_apps
        app_info = self.registry['core_apps'].get(app_key) or \
                   self.registry['default_apps'].get(app_key)

        if not app_info:
            return False, f"Unknown app: {app_key}"

        app_dir = self.parent_dir / f"hivematrix-{app_key}"

        if app_dir.exists():
            return True, f"{app_key} already exists"

        try:
            print(f"Cloning {app_info['name']}...")
            subprocess.run([
                'git', 'clone', app_info['git_url'], str(app_dir)
            ], check=True, cwd=str(self.parent_dir))

            return True, f"{app_key} cloned successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to clone {app_key}: {e}"

    def install_app(self, app_key: str) -> Tuple[bool, str]:
        """Install an app (clone + run install.sh)"""
        # Clone the app
        success, message = self.clone_app(app_key)
        if not success:
            return False, message

        app_dir = self.parent_dir / f"hivematrix-{app_key}"
        install_script = app_dir / "install.sh"

        if not install_script.exists():
            print(f"  No install.sh found for {app_key}, skipping...")
            return True, f"{app_key} cloned (no install script)"

        try:
            print(f"Running install script for {app_key}...")
            # Make it executable
            subprocess.run(['chmod', '+x', str(install_script)], check=True)

            # Run it
            subprocess.run([str(install_script)], check=True, cwd=str(app_dir))

            return True, f"{app_key} installed successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install {app_key}: {e}"

    def get_installed_apps(self) -> List[str]:
        """Get list of installed apps"""
        installed = []
        for app_key in list(self.registry['core_apps'].keys()) + list(self.registry['default_apps'].keys()):
            app_dir = self.parent_dir / f"hivematrix-{app_key}"
            if app_dir.exists():
                installed.append(app_key)
        return installed

    def get_app_status(self, app_key: str) -> Dict:
        """Get detailed status of an app"""
        app_dir = self.parent_dir / f"hivematrix-{app_key}"

        status = {
            'installed': app_dir.exists(),
            'git_url': None,
            'git_status': None,
            'git_branch': None,
            'has_updates': False
        }

        if not status['installed']:
            return status

        try:
            # Get git remote URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, check=True, cwd=str(app_dir)
            )
            status['git_url'] = result.stdout.strip()

            # Get current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True, text=True, check=True, cwd=str(app_dir)
            )
            status['git_branch'] = result.stdout.strip()

            # Check for updates (fetch first)
            subprocess.run(
                ['git', 'fetch'],
                capture_output=True, check=True, cwd=str(app_dir)
            )

            # Check if behind remote
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD..@{u}'],
                capture_output=True, text=True, check=True, cwd=str(app_dir)
            )
            commits_behind = int(result.stdout.strip())
            status['has_updates'] = commits_behind > 0
            status['commits_behind'] = commits_behind

            # Get git status
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, check=True, cwd=str(app_dir)
            )
            status['git_status'] = 'clean' if not result.stdout.strip() else 'modified'

        except subprocess.CalledProcessError:
            pass

        return status

    def git_pull_app(self, app_key: str) -> Tuple[bool, str]:
        """Pull latest changes for an app"""
        app_dir = self.parent_dir / f"hivematrix-{app_key}"

        if not app_dir.exists():
            return False, f"{app_key} not installed"

        try:
            result = subprocess.run(
                ['git', 'pull'],
                capture_output=True, text=True, check=True, cwd=str(app_dir)
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, f"Failed to pull {app_key}: {e.stderr}"

    def update_services_json(self):
        """Update services.json with installed apps"""
        installed = self.get_installed_apps()
        services = {}

        # Add Keycloak if installed
        # Load version from config file
        version_file = self.helm_dir / "keycloak_version.conf"
        keycloak_version = "26.4.0"  # default
        if version_file.exists():
            with open(version_file) as f:
                for line in f:
                    if line.startswith("KEYCLOAK_VERSION="):
                        keycloak_version = line.split("=")[1].strip()
                        break

        if (self.parent_dir / f"keycloak-{keycloak_version}").exists():
            services['keycloak'] = {
                "url": "http://localhost:8080",
                "path": f"../keycloak-{keycloak_version}",
                "port": 8080,
                "start_command": "bin/kc.sh start-dev",
                "type": "keycloak"
            }

        # Add Helm (the orchestration service itself)
        services['helm'] = {
            "url": "http://localhost:5004",
            "path": ".",
            "port": 5004,
            "python_bin": "pyenv/bin/python",
            "run_script": "run.py",
            "visible": True
        }

        # Add installed apps
        for app_key in installed:
            app_info = self.registry['core_apps'].get(app_key) or \
                      self.registry['default_apps'].get(app_key)
            if app_info:
                service_config = {
                    "url": f"http://localhost:{app_info['port']}",
                    "path": f"../hivematrix-{app_key}",
                    "port": app_info['port'],
                    "python_bin": "pyenv/bin/python",
                    "run_script": "run.py"
                }

                # Mark all services as visible in the side panel
                service_config['visible'] = True

                services[app_key] = service_config

        # Write services.json
        with open(self.services_json, 'w') as f:
            json.dump(services, f, indent=2)

        # Update master_services.json
        master_services = {}
        for key, value in services.items():
            master_services[key] = {
                "url": value['url'],
                "port": value['port']
            }

        with open(self.master_services_json, 'w') as f:
            json.dump(master_services, f, indent=2)


def main():
    manager = InstallManager()

    if len(sys.argv) < 2:
        print("Usage: install_manager.py <command> [args]")
        print("Commands:")
        print("  check-deps          - Check system dependencies")
        print("  install-dep <name>  - Install a system dependency")
        print("  clone <app>         - Clone an app")
        print("  install <app>       - Install an app")
        print("  status <app>        - Get app status")
        print("  pull <app>          - Pull latest changes")
        print("  list-installed      - List installed apps")
        print("  update-config       - Update services.json")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'check-deps':
        deps = manager.check_system_dependencies()
        print("\nSystem Dependencies:")
        for dep, installed in deps.items():
            status = "✓" if installed else "✗"
            print(f"  {status} {dep}")

    elif command == 'install-dep' and len(sys.argv) >= 3:
        dep_name = sys.argv[2]
        success, message = manager.install_system_dependency(dep_name)
        print(message)
        sys.exit(0 if success else 1)

    elif command == 'clone' and len(sys.argv) >= 3:
        app_key = sys.argv[2]
        success, message = manager.clone_app(app_key)
        print(message)
        sys.exit(0 if success else 1)

    elif command == 'install' and len(sys.argv) >= 3:
        app_key = sys.argv[2]
        success, message = manager.install_app(app_key)
        print(message)
        sys.exit(0 if success else 1)

    elif command == 'status' and len(sys.argv) >= 3:
        app_key = sys.argv[2]
        status = manager.get_app_status(app_key)
        print(json.dumps(status, indent=2))

    elif command == 'pull' and len(sys.argv) >= 3:
        app_key = sys.argv[2]
        success, message = manager.git_pull_app(app_key)
        print(message)
        sys.exit(0 if success else 1)

    elif command == 'list-installed':
        installed = manager.get_installed_apps()
        print("Installed apps:")
        for app in installed:
            print(f"  - {app}")

    elif command == 'update-config':
        manager.update_services_json()
        print("Updated services.json and master_services.json")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
