"""
Module Manager for HiveMatrix Helm

Handles installation, updating, and removal of HiveMatrix modules from git repos.
"""

import os
import subprocess
import json
import shutil
from pathlib import Path

class ModuleManager:
    """Manages HiveMatrix module installation and updates"""

    # Core system modules (cannot be removed)
    CORE_MODULES = {'core', 'nexus', 'helm'}

    # Predefined official modules
    OFFICIAL_MODULES = {
        'core': {
            'name': 'Core',
            'description': 'Authentication & JWT Token Management',
            'git_url': 'https://github.com/ruapotato/hivematrix-core.git',
            'port': 5000,
            'visible': False,
            'core_system': True
        },
        'nexus': {
            'name': 'Nexus',
            'description': 'Gateway & Reverse Proxy',
            'git_url': 'https://github.com/ruapotato/hivematrix-nexus.git',
            'port': 443,
            'visible': False,
            'core_system': True
        },
        'helm': {
            'name': 'Helm',
            'description': 'Service Manager & Orchestration',
            'git_url': 'https://github.com/ruapotato/hivematrix-helm.git',
            'port': 5004,
            'visible': False,
            'core_system': True
        },
        'codex': {
            'name': 'Codex',
            'description': 'Client, Ticket, and Contact Management',
            'git_url': 'https://github.com/ruapotato/hivematrix-codex.git',
            'port': 5010,
            'visible': True,
            'core_system': False
        },
        'ledger': {
            'name': 'Ledger',
            'description': 'Financial Accounting and Invoicing',
            'git_url': 'https://github.com/ruapotato/hivematrix-ledger.git',
            'port': 5030,
            'visible': True,
            'core_system': False
        },
        'knowledgetree': {
            'name': 'KnowledgeTree',
            'description': 'Documentation and Knowledge Base',
            'git_url': 'https://github.com/ruapotato/hivematrix-knowledgetree.git',
            'port': 5020,
            'visible': True,
            'core_system': False
        },
        'template': {
            'name': 'Template',
            'description': 'Template for creating new modules',
            'git_url': 'https://github.com/ruapotato/hivematrix-template.git',
            'port': 5040,
            'visible': False,
            'core_system': False
        }
    }

    @staticmethod
    def get_modules_dir():
        """Get the parent directory where modules are installed"""
        helm_dir = Path(__file__).parent.parent.absolute()
        return helm_dir.parent

    @staticmethod
    def list_installed_modules():
        """List all installed modules (excluding core system for display)"""
        modules_dir = ModuleManager.get_modules_dir()
        installed = []

        for item in modules_dir.iterdir():
            if item.is_dir() and item.name.startswith('hivematrix-'):
                module_id = item.name.replace('hivematrix-', '')

                # Skip core system modules in the module management UI
                if module_id in ModuleManager.CORE_MODULES:
                    continue

                # Check if it's a git repo
                is_git = (item / '.git').exists()

                # Try to get git remote URL
                git_url = None
                if is_git:
                    try:
                        result = subprocess.run(
                            ['git', '-C', str(item), 'config', '--get', 'remote.origin.url'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            git_url = result.stdout.strip()
                    except:
                        pass

                # Check if it's an official module
                official_info = ModuleManager.OFFICIAL_MODULES.get(module_id, {})

                installed.append({
                    'id': module_id,
                    'name': official_info.get('name', module_id.title()),
                    'description': official_info.get('description', 'Custom module'),
                    'path': str(item),
                    'git_url': git_url,
                    'is_git': is_git,
                    'is_official': module_id in ModuleManager.OFFICIAL_MODULES,
                    'is_core_system': module_id in ModuleManager.CORE_MODULES
                })

        return installed

    @staticmethod
    def list_available_modules():
        """List official modules that aren't installed (excluding core system)"""
        installed_ids = {m['id'] for m in ModuleManager.list_installed_modules()}
        # Also get all installed modules including core to check what's actually there
        modules_dir = ModuleManager.get_modules_dir()
        all_installed_ids = {
            item.name.replace('hivematrix-', '')
            for item in modules_dir.iterdir()
            if item.is_dir() and item.name.startswith('hivematrix-')
        }

        available = []

        for module_id, info in ModuleManager.OFFICIAL_MODULES.items():
            # Skip core system modules
            if module_id in ModuleManager.CORE_MODULES:
                continue

            # Only show if not installed
            if module_id not in all_installed_ids:
                available.append({
                    'id': module_id,
                    'name': info['name'],
                    'description': info['description'],
                    'git_url': info['git_url'],
                    'port': info['port']
                })

        return available

    @staticmethod
    def install_module(module_id_or_url, port=None, log_callback=None):
        """
        Install a module from git.

        Args:
            module_id_or_url: Either an official module ID or a git URL
            port: Port number (required if using custom URL)
            log_callback: Function to call with log messages (optional)

        Returns:
            tuple: (success: bool, message: str, module_id: str, logs: list)
        """
        modules_dir = ModuleManager.get_modules_dir()
        logs = []

        def log(msg):
            logs.append(msg)
            print(msg)
            if log_callback:
                log_callback(msg)

        # Check if it's an official module
        if module_id_or_url in ModuleManager.OFFICIAL_MODULES:
            module_info = ModuleManager.OFFICIAL_MODULES[module_id_or_url]
            git_url = module_info['git_url']
            module_id = module_id_or_url
            port = module_info['port']
            visible = module_info.get('visible', True)
        else:
            # Custom git URL
            git_url = module_id_or_url
            # Extract module name from URL
            module_id = git_url.rstrip('/').split('/')[-1].replace('.git', '').replace('hivematrix-', '')

            if not port:
                return False, "Port number required for custom modules", None, logs

            visible = True

        target_dir = modules_dir / f'hivematrix-{module_id}'

        # Check if already installed
        if target_dir.exists():
            return False, f"Module '{module_id}' is already installed", module_id, logs

        try:
            # Clone the repository
            log(f"=== Cloning {module_id} ===")
            log(f"URL: {git_url}")
            log(f"Target: {target_dir}")

            result = subprocess.run(
                ['git', 'clone', git_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                log(f"ERROR: Git clone failed")
                log(result.stderr)
                return False, f"Git clone failed: {result.stderr}", None, logs

            log("✓ Repository cloned successfully")

            # Run install.sh if it exists
            install_script = target_dir / 'install.sh'
            if install_script.exists():
                log(f"\n=== Running install.sh ===")

                # Make sure it's executable
                os.chmod(str(install_script), 0o755)

                result = subprocess.run(
                    ['bash', str(install_script)],
                    cwd=str(target_dir),
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                # Log stdout
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            log(line)

                # Log stderr
                if result.stderr:
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            log(f"STDERR: {line}")

                if result.returncode != 0:
                    log(f"WARNING: install.sh exited with code {result.returncode}")
                else:
                    log("✓ Install script completed successfully")
            else:
                log("Note: No install.sh found, skipping")

            # Verify pyenv was created
            log(f"\n=== Verifying Installation ===")
            pyenv_path = target_dir / 'pyenv'
            if pyenv_path.exists():
                log("✓ Python virtual environment (pyenv) created")

                # Check if python exists in pyenv
                python_bin = pyenv_path / 'bin' / 'python'
                if python_bin.exists():
                    log(f"✓ Python binary found at {python_bin}")
                else:
                    log(f"WARNING: Python binary not found in pyenv")
            else:
                log("WARNING: pyenv directory not found")
                log("  This may cause issues when starting the service")
                log("  The install.sh script may not have run correctly")

            # Check for run.py
            run_script = target_dir / 'run.py'
            if run_script.exists():
                log("✓ run.py found")
            else:
                log("WARNING: run.py not found - service may not start")

            # Register in services.json
            log(f"\n=== Registering service ===")
            ModuleManager.register_service(module_id, port, visible)
            log(f"✓ Registered {module_id} on port {port}")

            # Reload Helm's service configuration
            log("\n=== Reloading configuration ===")
            try:
                from flask import current_app
                services_file = Path(__file__).parent.parent / 'services.json'
                if services_file.exists():
                    with open(services_file, 'r') as f:
                        services = json.load(f)
                        current_app.config['SERVICES'] = services
                    log("✓ Helm configuration reloaded")
            except Exception as e:
                log(f"WARNING: Could not reload config: {e}")

            log(f"\n=== Installation Complete ===")
            log(f"Module '{module_id}' is now installed")
            log(f"Start the service from the main dashboard")

            return True, f"Module '{module_id}' installed successfully", module_id, logs

        except subprocess.TimeoutExpired:
            log("ERROR: Installation timed out")
            # Cleanup on timeout
            if target_dir.exists():
                shutil.rmtree(target_dir)
            return False, "Installation timed out", None, logs
        except Exception as e:
            log(f"ERROR: Installation failed: {str(e)}")
            # Cleanup on error
            if target_dir.exists():
                shutil.rmtree(target_dir)
            return False, f"Installation failed: {str(e)}", None, logs

    @staticmethod
    def remove_module(module_id):
        """
        Remove an installed module.

        Args:
            module_id: The module identifier (without 'hivematrix-' prefix)

        Returns:
            tuple: (success: bool, message: str)
        """
        # Don't allow removing core system modules
        if module_id in ModuleManager.CORE_MODULES:
            return False, f"Cannot remove core system module '{module_id}'"

        modules_dir = ModuleManager.get_modules_dir()
        target_dir = modules_dir / f'hivematrix-{module_id}'

        if not target_dir.exists():
            return False, f"Module '{module_id}' is not installed"

        try:
            # Remove from services.json
            ModuleManager.unregister_service(module_id)

            # Remove directory
            shutil.rmtree(target_dir)

            return True, f"Module '{module_id}' removed successfully"

        except Exception as e:
            return False, f"Failed to remove module: {str(e)}"

    @staticmethod
    def update_module(module_id):
        """
        Update a module from git.

        Args:
            module_id: The module identifier

        Returns:
            tuple: (success: bool, message: str, logs: list)
        """
        modules_dir = ModuleManager.get_modules_dir()
        target_dir = modules_dir / f'hivematrix-{module_id}'
        logs = []

        def log(msg):
            logs.append(msg)
            print(msg)

        if not target_dir.exists():
            return False, f"Module '{module_id}' is not installed", logs

        if not (target_dir / '.git').exists():
            return False, f"Module '{module_id}' is not a git repository", logs

        try:
            # Git pull
            log(f"=== Updating {module_id} ===")
            log(f"Running git pull...")

            result = subprocess.run(
                ['git', '-C', str(target_dir), 'pull'],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Log git output
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        log(line)

            if result.returncode != 0:
                log(f"ERROR: Git pull failed")
                if result.stderr:
                    log(result.stderr)
                return False, f"Git pull failed: {result.stderr}", logs

            log("✓ Repository updated successfully")

            # Run install.sh if it exists
            install_script = target_dir / 'install.sh'
            if install_script.exists():
                log(f"\n=== Running install.sh ===")

                # Make sure it's executable
                os.chmod(str(install_script), 0o755)

                result = subprocess.run(
                    ['bash', str(install_script)],
                    cwd=str(target_dir),
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                # Log stdout
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            log(line)

                # Log stderr
                if result.stderr:
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            log(f"STDERR: {line}")

                if result.returncode != 0:
                    log(f"WARNING: install.sh exited with code {result.returncode}")
                else:
                    log("✓ Install script completed successfully")
            else:
                log("Note: No install.sh found, skipping")

            log(f"\n=== Update Complete ===")
            log(f"Module '{module_id}' has been updated")
            log(f"Restart the service from the main dashboard if needed")

            return True, f"Module '{module_id}' updated successfully", logs

        except Exception as e:
            log(f"ERROR: Update failed: {str(e)}")
            return False, f"Update failed: {str(e)}", logs

    @staticmethod
    def register_service(module_id, port, visible=True):
        """Add a module to services.json with full configuration"""
        helm_dir = Path(__file__).parent.parent
        services_file = helm_dir / 'services.json'

        try:
            # Load existing services
            if services_file.exists():
                with open(services_file, 'r') as f:
                    services = json.load(f)
            else:
                services = {}

            # Add new service with full configuration
            services[module_id] = {
                "url": f"http://localhost:{port}",
                "path": f"../hivematrix-{module_id}",
                "port": port,
                "python_bin": "pyenv/bin/python",
                "run_script": "run.py",
                "visible": visible
            }

            # Save
            with open(services_file, 'w') as f:
                json.dump(services, f, indent=4)

            print(f"  ✓ Registered {module_id} with full service configuration")

        except Exception as e:
            print(f"Warning: Could not register service: {e}")

    @staticmethod
    def unregister_service(module_id):
        """Remove a module from services.json"""
        helm_dir = Path(__file__).parent.parent
        services_file = helm_dir / 'services.json'

        try:
            if services_file.exists():
                with open(services_file, 'r') as f:
                    services = json.load(f)

                if module_id in services:
                    del services[module_id]

                    with open(services_file, 'w') as f:
                        json.dump(services, f, indent=4)

        except Exception as e:
            print(f"Warning: Could not unregister service: {e}")
