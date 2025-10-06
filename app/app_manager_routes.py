"""
API routes for app installation and management
"""

from flask import request, jsonify, g
from app import app
from app.auth import token_required, admin_required
import json
import sys
from pathlib import Path

# Add parent directory to path to import our managers
sys.path.insert(0, str(Path(__file__).parent.parent))

from install_manager import InstallManager
from config_manager import ConfigManager

install_manager = InstallManager()
config_manager = ConfigManager()


# ============================================================
# App Discovery and Registry
# ============================================================

@app.route('/api/apps/registry', methods=['GET'])
@token_required
def get_app_registry():
    """Get the registry of available apps"""
    return jsonify(install_manager.registry)


@app.route('/api/apps/available', methods=['GET'])
@token_required
def list_available_apps():
    """List all available apps (both core and default)"""
    registry = install_manager.registry
    apps = {}

    # Combine core and default apps
    for app_key, app_info in registry.get('core_apps', {}).items():
        apps[app_key] = {
            **app_info,
            'category': 'core',
            'installed': (install_manager.parent_dir / f"hivematrix-{app_key}").exists()
        }

    for app_key, app_info in registry.get('default_apps', {}).items():
        apps[app_key] = {
            **app_info,
            'category': 'default',
            'installed': (install_manager.parent_dir / f"hivematrix-{app_key}").exists()
        }

    return jsonify({
        'apps': apps,
        'system_dependencies': registry.get('system_dependencies', {})
    })


@app.route('/api/apps/installed', methods=['GET'])
@token_required
def list_installed_apps():
    """List all installed apps"""
    installed = install_manager.get_installed_apps()
    apps = {}

    for app_key in installed:
        status = install_manager.get_app_status(app_key)
        app_info = install_manager.registry.get('core_apps', {}).get(app_key) or \
                   install_manager.registry.get('default_apps', {}).get(app_key)

        if app_info:
            apps[app_key] = {
                **app_info,
                **status
            }

    return jsonify({'apps': apps})


# ============================================================
# System Dependencies
# ============================================================

@app.route('/api/dependencies/check', methods=['GET'])
@token_required
def check_dependencies():
    """Check which system dependencies are installed"""
    deps = install_manager.check_system_dependencies()
    return jsonify({'dependencies': deps})


@app.route('/api/dependencies/<dep_name>/install', methods=['POST'])
@admin_required
def install_dependency(dep_name):
    """Install a system dependency"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    success, message = install_manager.install_system_dependency(dep_name)

    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


# ============================================================
# App Installation
# ============================================================

@app.route('/api/apps/<app_key>/clone', methods=['POST'])
@admin_required
def clone_app(app_key):
    """Clone an app from its git repository"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    success, message = install_manager.clone_app(app_key)

    # Update services.json after cloning
    if success:
        install_manager.update_services_json()

    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


@app.route('/api/apps/<app_key>/install', methods=['POST'])
@admin_required
def install_app(app_key):
    """Install an app (clone + run install script)"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    success, message = install_manager.install_app(app_key)

    # Update services.json after installation
    if success:
        install_manager.update_services_json()

    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


@app.route('/api/apps/install-from-git', methods=['POST'])
@admin_required
def install_from_git():
    """Install an app from a custom git URL"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    data = request.get_json()
    git_url = data.get('git_url')
    app_name = data.get('app_name')
    port = data.get('port', 5099)

    if not git_url or not app_name:
        return {'error': 'git_url and app_name are required'}, 400

    # Clone the repository
    import subprocess
    try:
        app_dir = install_manager.parent_dir / f"hivematrix-{app_name}"
        if app_dir.exists():
            return {'error': f'{app_name} already exists'}, 400

        subprocess.run(
            ['git', 'clone', git_url, str(app_dir)],
            check=True,
            cwd=str(install_manager.parent_dir)
        )

        # Run install script if it exists
        install_script = app_dir / "install.sh"
        if install_script.exists():
            subprocess.run(['chmod', '+x', str(install_script)], check=True)
            subprocess.run([str(install_script)], check=True, cwd=str(app_dir))

        # Update services.json
        install_manager.update_services_json()

        return jsonify({
            'success': True,
            'message': f'{app_name} installed successfully from {git_url}'
        })

    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'message': f'Failed to install {app_name}: {str(e)}'
        }), 400


# ============================================================
# Git Operations
# ============================================================

@app.route('/api/apps/<app_key>/status', methods=['GET'])
@token_required
def get_app_status(app_key):
    """Get detailed status of an app including git info"""
    status = install_manager.get_app_status(app_key)
    return jsonify(status)


@app.route('/api/apps/<app_key>/git/pull', methods=['POST'])
@admin_required
def git_pull_app(app_key):
    """Pull latest changes from git for an app"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    success, message = install_manager.git_pull_app(app_key)

    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


@app.route('/api/apps/<app_key>/git/status', methods=['GET'])
@token_required
def git_status_app(app_key):
    """Get git status for an app"""
    import subprocess

    app_dir = install_manager.parent_dir / f"hivematrix-{app_key}"
    if not app_dir.exists():
        return {'error': f'{app_key} not installed'}, 404

    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain', '--branch'],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(app_dir)
        )

        return jsonify({
            'app': app_key,
            'status': result.stdout,
            'clean': len(result.stdout.strip()) == 0
        })
    except subprocess.CalledProcessError as e:
        return {'error': f'Failed to get git status: {e.stderr}'}, 400


# ============================================================
# Configuration Management
# ============================================================

@app.route('/api/apps/<app_key>/config', methods=['GET'])
@token_required
def get_app_config(app_key):
    """Get configuration for an app"""
    config = config_manager.get_app_config(app_key)
    return jsonify(config)


@app.route('/api/apps/<app_key>/config', methods=['PUT'])
@admin_required
def update_app_config(app_key):
    """Update configuration for an app"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    data = request.get_json()
    config_manager.update_app_config(app_key, data)

    return jsonify({
        'success': True,
        'message': f'Configuration updated for {app_key}'
    })


@app.route('/api/apps/<app_key>/config/sync', methods=['POST'])
@admin_required
def sync_app_config(app_key):
    """Sync configuration to app directory (.flaskenv and instance/app.conf)"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    try:
        config_manager.write_app_dotenv(app_key)
        config_manager.write_app_conf(app_key)

        return jsonify({
            'success': True,
            'message': f'Configuration synced to {app_key}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400


@app.route('/api/config/sync-all', methods=['POST'])
@admin_required
def sync_all_configs():
    """Sync configuration to all installed apps"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    try:
        config_manager.sync_all_apps()
        return jsonify({
            'success': True,
            'message': 'Configuration synced to all apps'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400


# ============================================================
# Database Management
# ============================================================

@app.route('/api/apps/<app_key>/database/setup', methods=['POST'])
@admin_required
def setup_app_database(app_key):
    """Setup PostgreSQL database for an app"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    data = request.get_json() or {}
    db_name = data.get('db_name')
    db_user = data.get('db_user')
    db_password = data.get('db_password')

    success, message = config_manager.setup_app_database(
        app_key, db_name, db_user, db_password
    )

    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 400


# ============================================================
# Utility Routes
# ============================================================

@app.route('/api/apps/update-registry', methods=['POST'])
@admin_required
def update_service_registry():
    """Update services.json based on installed apps"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    try:
        install_manager.update_services_json()
        return jsonify({
            'success': True,
            'message': 'Service registry updated'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
