"""
API routes for service control and log ingestion
"""

from flask import request, jsonify, g
from app import app
from app.auth import token_required, admin_required
from app.service_manager import ServiceManager
from extensions import db
from models import LogEntry, ServiceStatus, ServiceMetric
from datetime import datetime, timedelta

# ============================================================
# Service Control API
# ============================================================

@app.route('/api/services', methods=['GET'])
@token_required
def list_services():
    """List all configured services"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    services = ServiceManager.get_all_services()
    return jsonify({
        'services': list(services.keys()),
        'details': services
    })


@app.route('/api/services/status', methods=['GET'])
@token_required
def all_services_status():
    """Get status of all services"""
    statuses = ServiceManager.get_all_service_statuses()
    return jsonify(statuses)


@app.route('/api/services/<service_name>/status', methods=['GET'])
@token_required
def service_status(service_name):
    """Get status of a specific service"""
    try:
        status = ServiceManager.get_service_status(service_name)
        return jsonify(status)
    except ValueError as e:
        return {'error': str(e)}, 404


@app.route('/api/services/<service_name>/start', methods=['POST'])
@admin_required
def start_service(service_name):
    """Start a service"""
    data = request.get_json() or {}
    mode = data.get('mode', 'development')

    if mode not in ['development', 'production']:
        return {'error': 'Invalid mode. Must be development or production'}, 400

    result = ServiceManager.start_service(service_name, mode)
    status_code = 200 if result['success'] else 400

    return jsonify(result), status_code


@app.route('/api/services/<service_name>/stop', methods=['POST'])
@admin_required
def stop_service(service_name):
    """Stop a service"""
    result = ServiceManager.stop_service(service_name)
    status_code = 200 if result['success'] else 400

    return jsonify(result), status_code


@app.route('/api/services/<service_name>/restart', methods=['POST'])
@admin_required
def restart_service(service_name):
    """Restart a service"""
    data = request.get_json() or {}
    mode = data.get('mode', 'development')

    if mode not in ['development', 'production']:
        return {'error': 'Invalid mode. Must be development or production'}, 400

    result = ServiceManager.restart_service(service_name, mode)
    status_code = 200 if result['success'] else 400

    return jsonify(result), status_code


# ============================================================
# Log Ingestion API
# ============================================================

@app.route('/api/logs/ingest', methods=['POST'])
@token_required
def ingest_logs():
    """
    Accept logs from other HiveMatrix services.
    This endpoint accepts both single log entries and batches.

    Expected format:
    {
        "service_name": "codex",
        "logs": [
            {
                "level": "INFO",
                "message": "Service started",
                "context": {"key": "value"},
                "trace_id": "uuid",
                "user_id": "user@example.com"
            }
        ]
    }
    """
    data = request.get_json()

    if not data or 'logs' not in data:
        return {'error': 'Missing logs array'}, 400

    service_name = data.get('service_name')

    # If this is a service-to-service call, use the calling service name
    if g.is_service_call and not service_name:
        service_name = g.service

    if not service_name:
        return {'error': 'service_name is required'}, 400

    logs = data.get('logs', [])
    ingested = 0

    try:
        for log_data in logs:
            log_entry = LogEntry(
                service_name=service_name,
                level=log_data.get('level', 'INFO'),
                message=log_data.get('message', ''),
                context=log_data.get('context'),
                trace_id=log_data.get('trace_id'),
                user_id=log_data.get('user_id'),
                hostname=log_data.get('hostname'),
                process_id=log_data.get('process_id'),
                timestamp=log_data.get('timestamp') or datetime.utcnow()
            )
            db.session.add(log_entry)
            ingested += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'ingested': ingested,
            'message': f'Successfully ingested {ingested} log entries'
        })

    except Exception as e:
        db.session.rollback()
        return {'error': f'Failed to ingest logs: {str(e)}'}, 500


@app.route('/api/logs', methods=['GET'])
@token_required
def get_logs():
    """
    Retrieve logs with filtering options

    Query parameters:
    - service: Filter by service name
    - level: Filter by log level
    - start_time: ISO format datetime
    - end_time: ISO format datetime
    - limit: Number of records (default 100, max 1000)
    - offset: Pagination offset
    - trace_id: Filter by trace ID
    """
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Build query
    query = LogEntry.query

    # Filters
    service = request.args.get('service')
    if service:
        query = query.filter_by(service_name=service)

    level = request.args.get('level')
    if level:
        query = query.filter_by(level=level.upper())

    trace_id = request.args.get('trace_id')
    if trace_id:
        query = query.filter_by(trace_id=trace_id)

    # Time range
    start_time = request.args.get('start_time')
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            query = query.filter(LogEntry.timestamp >= start_dt)
        except ValueError:
            return {'error': 'Invalid start_time format'}, 400

    end_time = request.args.get('end_time')
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            query = query.filter(LogEntry.timestamp <= end_dt)
        except ValueError:
            return {'error': 'Invalid end_time format'}, 400

    # Pagination
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    # Execute query
    query = query.order_by(LogEntry.timestamp.desc())
    total = query.count()
    logs = query.limit(limit).offset(offset).all()

    return jsonify({
        'total': total,
        'limit': limit,
        'offset': offset,
        'logs': [log.to_dict() for log in logs]
    })


@app.route('/api/logs/<int:log_id>', methods=['GET'])
@token_required
def get_log(log_id):
    """Get a specific log entry by ID"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    log = LogEntry.query.get(log_id)

    if not log:
        return {'error': 'Log entry not found'}, 404

    return jsonify(log.to_dict())


# ============================================================
# Metrics API
# ============================================================

@app.route('/api/metrics/<service_name>', methods=['GET'])
@token_required
def get_service_metrics(service_name):
    """
    Get metrics for a service

    Query parameters:
    - metric_name: Filter by metric name
    - start_time: ISO format datetime
    - end_time: ISO format datetime
    - limit: Number of records (default 100)
    """
    query = ServiceMetric.query.filter_by(service_name=service_name)

    metric_name = request.args.get('metric_name')
    if metric_name:
        query = query.filter_by(metric_name=metric_name)

    # Time range - default to last 24 hours
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    start_param = request.args.get('start_time')
    if start_param:
        try:
            start_time = datetime.fromisoformat(start_param)
        except ValueError:
            return {'error': 'Invalid start_time format'}, 400

    end_param = request.args.get('end_time')
    if end_param:
        try:
            end_time = datetime.fromisoformat(end_param)
        except ValueError:
            return {'error': 'Invalid end_time format'}, 400

    query = query.filter(ServiceMetric.timestamp >= start_time)
    query = query.filter(ServiceMetric.timestamp <= end_time)

    limit = min(int(request.args.get('limit', 100)), 1000)

    metrics = query.order_by(ServiceMetric.timestamp.desc()).limit(limit).all()

    return jsonify({
        'service_name': service_name,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'metrics': [m.to_dict() for m in metrics]
    })


# ============================================================
# Keycloak User Management API
# ============================================================

import requests as http_requests

def get_keycloak_admin_token():
    """Get admin token for Keycloak API calls"""
    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    # Use admin credentials from config or environment
    admin_user = app.config.get('KEYCLOAK_ADMIN_USER', 'admin')
    admin_pass = app.config.get('KEYCLOAK_ADMIN_PASS', 'admin')

    token_url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"

    response = http_requests.post(token_url, data={
        'client_id': 'admin-cli',
        'username': admin_user,
        'password': admin_pass,
        'grant_type': 'password'
    })

    if response.status_code == 200:
        return response.json().get('access_token')
    return None


@app.route('/api/keycloak/users', methods=['GET'])
@admin_required
def list_keycloak_users():
    """List all users in Keycloak"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    users_url = f"{keycloak_url}/admin/realms/{realm}/users"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.get(users_url, headers=headers)

    if response.status_code == 200:
        return jsonify({'users': response.json()})
    return {'error': 'Failed to fetch users'}, response.status_code


@app.route('/api/keycloak/users', methods=['POST'])
@admin_required
def create_keycloak_user():
    """Create a new user in Keycloak"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    data = request.get_json()
    if not data or not data.get('username') or not data.get('email'):
        return {'error': 'username and email are required'}, 400

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    users_url = f"{keycloak_url}/admin/realms/{realm}/users"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    user_data = {
        'username': data['username'],
        'email': data['email'],
        'firstName': data.get('firstName', ''),
        'lastName': data.get('lastName', ''),
        'enabled': data.get('enabled', True),
        'emailVerified': data.get('emailVerified', False)
    }

    response = http_requests.post(users_url, json=user_data, headers=headers)

    if response.status_code == 201:
        return {'success': True, 'message': 'User created successfully'}, 201
    return {'error': 'Failed to create user', 'details': response.text}, response.status_code


@app.route('/api/keycloak/users/<user_id>', methods=['PUT'])
@admin_required
def update_keycloak_user(user_id):
    """Update a user in Keycloak"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    data = request.get_json()
    if not data:
        return {'error': 'No data provided'}, 400

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    user_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    response = http_requests.put(user_url, json=data, headers=headers)

    if response.status_code == 204:
        return {'success': True, 'message': 'User updated successfully'}
    return {'error': 'Failed to update user'}, response.status_code


@app.route('/api/keycloak/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_keycloak_user(user_id):
    """Delete a user from Keycloak"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    user_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.delete(user_url, headers=headers)

    if response.status_code == 204:
        return {'success': True, 'message': 'User deleted successfully'}
    return {'error': 'Failed to delete user'}, response.status_code


@app.route('/api/keycloak/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Reset a user's password"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    data = request.get_json()
    password = data.get('password')
    temporary = data.get('temporary', True)

    if not password:
        return {'error': 'password is required'}, 400

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    password_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}/reset-password"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    password_data = {
        'type': 'password',
        'value': password,
        'temporary': temporary
    }

    response = http_requests.put(password_url, json=password_data, headers=headers)

    if response.status_code == 204:
        return {'success': True, 'message': 'Password reset successfully'}
    return {'error': 'Failed to reset password'}, response.status_code


@app.route('/api/keycloak/groups', methods=['GET'])
@admin_required
def list_keycloak_groups():
    """List all groups in Keycloak"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    groups_url = f"{keycloak_url}/admin/realms/{realm}/groups"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.get(groups_url, headers=headers)

    if response.status_code == 200:
        return jsonify({'groups': response.json()})
    return {'error': 'Failed to fetch groups'}, response.status_code


@app.route('/api/keycloak/users/<user_id>/groups', methods=['GET'])
@admin_required
def get_user_groups(user_id):
    """Get groups for a user"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    groups_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}/groups"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.get(groups_url, headers=headers)

    if response.status_code == 200:
        return jsonify({'groups': response.json()})
    return {'error': 'Failed to fetch user groups'}, response.status_code


@app.route('/api/keycloak/users/<user_id>/groups/<group_id>', methods=['PUT'])
@admin_required
def add_user_to_group(user_id, group_id):
    """Add user to a group"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    group_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}/groups/{group_id}"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.put(group_url, headers=headers)

    if response.status_code == 204:
        return {'success': True, 'message': 'User added to group'}
    return {'error': 'Failed to add user to group'}, response.status_code


@app.route('/api/keycloak/users/<user_id>/groups/<group_id>', methods=['DELETE'])
@admin_required
def remove_user_from_group(user_id, group_id):
    """Remove user from a group"""
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    group_url = f"{keycloak_url}/admin/realms/{realm}/users/{user_id}/groups/{group_id}"
    headers = {'Authorization': f'Bearer {token}'}

    response = http_requests.delete(group_url, headers=headers)

    if response.status_code == 204:
        return {'success': True, 'message': 'User removed from group'}
    return {'error': 'Failed to remove user from group'}, response.status_code


# ============================================================
# Security Audit API
# ============================================================

@app.route('/api/security/audit', methods=['GET'])
@token_required
def security_audit():
    """Run security audit on all services"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    import sys
    import os

    # Add security_audit module to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from security_audit import SecurityAuditor

        auditor = SecurityAuditor()
        findings = auditor.audit_services()

        return jsonify(findings)
    except Exception as e:
        return {'error': f'Security audit failed: {str(e)}'}, 500


@app.route('/api/security/firewall-script', methods=['GET'])
@admin_required
def generate_firewall_script():
    """Generate firewall configuration script"""
    import sys
    import os

    # Add security_audit module to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from security_audit import SecurityAuditor

        auditor = SecurityAuditor()

        # Get script type from query param
        script_type = request.args.get('type', 'ufw')

        if script_type == 'iptables':
            script = auditor.generate_iptables_rules()
            filename = 'secure_iptables.sh'
        else:
            script = auditor.generate_firewall_rules()
            filename = 'secure_firewall.sh'

        return jsonify({
            'success': True,
            'script': script,
            'filename': filename,
            'type': script_type
        })
    except Exception as e:
        return {'error': f'Failed to generate firewall script: {str(e)}'}, 500


# ============================================================
# Health Check
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': 'helm',
        'timestamp': datetime.utcnow().isoformat()
    })
