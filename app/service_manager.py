"""
Service Discovery and Process Management for HiveMatrix Helm

This module handles:
- Starting and stopping services
- Monitoring service health
- Collecting service metrics
"""

import os
import subprocess
import psutil
import signal
import time
import requests
import json
import shutil
from datetime import datetime
from flask import current_app
from extensions import db
from models import ServiceStatus, ServiceMetric

class ServiceManager:
    """Manages HiveMatrix services"""

    @staticmethod
    def sync_master_services_config(service_path):
        """
        Syncs the master services configuration to a service's directory.
        This ensures all services have a consistent view of the ecosystem.
        """
        # Path to master config
        helm_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        master_config_path = os.path.join(helm_dir, 'services.json')

        if not os.path.exists(master_config_path):
            return  # No master config to sync

        # Target services.json in the service directory
        target_config_path = os.path.join(service_path, 'services.json')

        try:
            # Load master config
            with open(master_config_path, 'r') as f:
                master_config = json.load(f)

            # Create simplified version for services (just url)
            # Filter out internal services for user-facing services like Nexus
            simplified_config = {}
            service_dir_name = os.path.basename(service_path)

            for service_name, service_info in master_config.items():
                # For Nexus, only include services marked as visible
                if service_dir_name == 'hivematrix-nexus':
                    if service_info.get('visible', False):
                        simplified_config[service_name] = {
                            "url": service_info["url"]
                        }
                else:
                    # For other services, include all
                    simplified_config[service_name] = {
                        "url": service_info["url"]
                    }

            # Write to service's services.json
            with open(target_config_path, 'w') as f:
                json.dump(simplified_config, f, indent=4)

            print(f"  ✓ Synced services config to {os.path.basename(service_path)}")
        except Exception as e:
            print(f"  Warning: Could not sync services config: {e}")

    @staticmethod
    def get_service_config(service_name):
        """Get configuration for a specific service"""
        services = current_app.config.get('SERVICES', {})
        if service_name not in services:
            raise ValueError(f"Service '{service_name}' not found in configuration")
        return services[service_name]

    @staticmethod
    def get_all_services():
        """Get all configured services"""
        return current_app.config.get('SERVICES', {})

    @staticmethod
    def is_process_running(pid):
        """Check if a process with given PID is running"""
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @staticmethod
    def get_process_info(pid):
        """Get detailed information about a process"""
        try:
            process = psutil.Process(pid)
            return {
                'pid': pid,
                'status': process.status(),
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_mb': process.memory_info().rss / (1024 * 1024),
                'create_time': datetime.fromtimestamp(process.create_time())
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    @staticmethod
    def find_service_process(service_name, port):
        """Find a running process for a service by port"""
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    # Accept Python or Java (Keycloak) processes
                    if 'python' in process.name().lower() or 'java' in process.name().lower():
                        return process.pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return None

    @staticmethod
    def get_log_file_paths(service_name):
        """Get the log file paths for a service"""
        helm_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(helm_dir, 'logs')

        # Ensure logs directory exists
        os.makedirs(logs_dir, exist_ok=True)

        stdout_path = os.path.join(logs_dir, f'{service_name}.stdout.log')
        stderr_path = os.path.join(logs_dir, f'{service_name}.stderr.log')

        return stdout_path, stderr_path

    @staticmethod
    def start_service(service_name, mode='development'):
        """
        Start a HiveMatrix service

        Args:
            service_name: Name of the service to start
            mode: 'development' or 'production'

        Returns:
            dict with status and details
        """
        config = ServiceManager.get_service_config(service_name)
        service_path = config.get('path')
        service_type = config.get('type', 'python')
        port = config.get('port')

        if not service_path:
            return {'success': False, 'message': 'Service path not configured'}

        # Resolve absolute path
        abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', service_path))

        if not os.path.exists(abs_path):
            return {'success': False, 'message': f'Service directory not found: {abs_path}'}

        # Check if already running
        existing_pid = ServiceManager.find_service_process(service_name, port)
        if existing_pid:
            return {'success': False, 'message': f'Service already running (PID: {existing_pid})'}

        # Sync master services configuration (skip for Keycloak)
        if service_type != 'keycloak':
            ServiceManager.sync_master_services_config(abs_path)

        # Get log file paths
        stdout_path, stderr_path = ServiceManager.get_log_file_paths(service_name)

        try:
            # Handle Keycloak differently
            if service_type == 'keycloak':
                start_command = config.get('start_command')
                if not start_command:
                    return {'success': False, 'message': 'Keycloak start command not configured'}

                # Parse command into list
                cmd_parts = start_command.split()
                cmd_path = os.path.join(abs_path, cmd_parts[0])

                if not os.path.exists(cmd_path):
                    return {'success': False, 'message': f'Keycloak executable not found: {cmd_path}'}

                # Set environment for Keycloak with admin credentials
                env = os.environ.copy()
                env['KEYCLOAK_ADMIN'] = 'admin'
                env['KEYCLOAK_ADMIN_PASSWORD'] = 'admin'

                # Open log files
                stdout_file = open(stdout_path, 'w')
                stderr_file = open(stderr_path, 'w')

                # Start Keycloak
                process = subprocess.Popen(
                    [cmd_path] + cmd_parts[1:],
                    cwd=abs_path,
                    env=env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True
                )
            else:
                # Standard Python service
                python_bin = config.get('python_bin', 'pyenv/bin/python')
                run_script = config.get('run_script', 'run.py')

                python_path = os.path.join(abs_path, python_bin)
                run_path = os.path.join(abs_path, run_script)

                if not os.path.exists(python_path):
                    return {'success': False, 'message': f'Python executable not found: {python_path}'}

                if not os.path.exists(run_path):
                    return {'success': False, 'message': f'Run script not found: {run_path}'}

                # Set environment for the service
                env = os.environ.copy()

                # Check if we're in dev mode from start.sh
                dev_mode = os.environ.get('HIVEMATRIX_DEV_MODE', 'false').lower() == 'true'

                if mode == 'development' or dev_mode:
                    env['FLASK_ENV'] = 'development'
                else:
                    env['FLASK_ENV'] = 'production'

                # Special handling for Nexus: set port 443 and use gunicorn (unless dev mode)
                if service_name == 'nexus':
                    env['NEXUS_PORT'] = '443'
                    env['NEXUS_HOST'] = '0.0.0.0'
                    # Use gunicorn by default in production mode
                    if not dev_mode:
                        env['USE_GUNICORN'] = 'true'
                    port = 443  # Update port variable for database storage

                # Load .flaskenv file if it exists
                flaskenv_path = os.path.join(abs_path, '.flaskenv')
                if os.path.exists(flaskenv_path):
                    with open(flaskenv_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip comments and empty lines
                            if line and not line.startswith('#'):
                                # Handle KEY=value or KEY='value' or KEY="value"
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip()
                                    # Remove quotes if present
                                    if value.startswith('"') and value.endswith('"'):
                                        value = value[1:-1]
                                    elif value.startswith("'") and value.endswith("'"):
                                        value = value[1:-1]
                                    env[key] = value

                # Open log files
                stdout_file = open(stdout_path, 'w')
                stderr_file = open(stderr_path, 'w')

                # Start process in background
                process = subprocess.Popen(
                    [python_path, run_path],
                    cwd=abs_path,
                    env=env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True  # Detach from parent
                )

            # Wait a moment to check if it started successfully
            time.sleep(2)

            if process.poll() is not None:
                # Process died immediately - read error from log files
                stderr_content = ''
                try:
                    with open(stderr_path, 'r') as f:
                        stderr_content = f.read()
                except:
                    pass
                return {
                    'success': False,
                    'message': f'Service failed to start. Check logs for details: {stderr_content[:500]}'
                }

            # Update database
            status = ServiceStatus.query.filter_by(service_name=service_name).first()
            if not status:
                status = ServiceStatus(service_name=service_name)
                db.session.add(status)

            status.status = 'running'
            status.pid = process.pid
            status.port = port
            status.started_at = datetime.utcnow()
            status.last_checked = datetime.utcnow()
            db.session.commit()

            return {
                'success': True,
                'message': f'Service started successfully',
                'pid': process.pid,
                'port': port
            }

        except Exception as e:
            return {'success': False, 'message': f'Failed to start service: {str(e)}'}

    @staticmethod
    def stop_service(service_name):
        """
        Stop a HiveMatrix service

        Args:
            service_name: Name of the service to stop

        Returns:
            dict with status and details
        """
        status = ServiceStatus.query.filter_by(service_name=service_name).first()

        if not status or not status.pid:
            return {'success': False, 'message': 'Service not running or PID unknown'}

        pid = status.pid

        if not ServiceManager.is_process_running(pid):
            # Update status
            status.status = 'stopped'
            status.pid = None
            db.session.commit()
            return {'success': False, 'message': 'Service was not running'}

        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)

            # Wait up to 10 seconds for graceful shutdown
            for _ in range(10):
                if not ServiceManager.is_process_running(pid):
                    break
                time.sleep(1)

            # Force kill if still running
            if ServiceManager.is_process_running(pid):
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)

            # Update database
            status.status = 'stopped'
            status.pid = None
            status.last_checked = datetime.utcnow()
            db.session.commit()

            return {'success': True, 'message': 'Service stopped successfully'}

        except ProcessLookupError:
            status.status = 'stopped'
            status.pid = None
            db.session.commit()
            return {'success': True, 'message': 'Service was already stopped'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to stop service: {str(e)}'}

    @staticmethod
    def restart_service(service_name, mode='development'):
        """Restart a service"""
        stop_result = ServiceManager.stop_service(service_name)
        time.sleep(2)  # Wait for cleanup
        start_result = ServiceManager.start_service(service_name, mode)

        return {
            'success': start_result['success'],
            'message': f"Stop: {stop_result['message']}. Start: {start_result['message']}",
            'details': {'stop': stop_result, 'start': start_result}
        }

    @staticmethod
    def get_service_status(service_name):
        """Get current status of a service"""
        config = ServiceManager.get_service_config(service_name)
        status = ServiceStatus.query.filter_by(service_name=service_name).first()

        result = {
            'service_name': service_name,
            'configured_port': config.get('port'),
            'configured_url': config.get('url'),
            'status': 'unknown',
            'health': 'unknown'
        }

        # Special case for services without DB tracking (Helm, Keycloak)
        if service_name in ['helm', 'keycloak']:
            port = config.get('port')
            if port:
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            connections = proc.net_connections()
                            for conn in connections:
                                if conn.laddr.port == port and conn.status == 'LISTEN':
                                    proc_info = ServiceManager.get_process_info(proc.pid)
                                    if proc_info:
                                        result.update(proc_info)
                                        result['status'] = 'running'
                                        result['pid'] = proc.pid
                                    break
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            continue

                    # If we didn't find a process, mark as stopped
                    if result['status'] == 'unknown':
                        result['status'] = 'stopped'
                except Exception:
                    result['status'] = 'stopped'

        elif status:
            result.update(status.to_dict())

            # Check if process is actually running
            if status.pid and ServiceManager.is_process_running(status.pid):
                proc_info = ServiceManager.get_process_info(status.pid)
                if proc_info:
                    result.update(proc_info)
                    result['status'] = 'running'
            else:
                result['status'] = 'stopped'
                result['pid'] = None

        # Try health check - try /health first, fall back to root /
        health_endpoints = ['/health', '/']
        health_checked = False

        for endpoint in health_endpoints:
            try:
                response = requests.get(f"{config['url']}{endpoint}", timeout=2)
                if response.status_code == 200:
                    result['health'] = 'healthy'
                    result['health_message'] = f'Service responding at {endpoint}'
                    health_checked = True
                    break
                elif endpoint == '/':
                    # Even non-200 from root means service is responding
                    result['health'] = 'degraded'
                    result['health_message'] = f'HTTP {response.status_code} at {endpoint}'
                    health_checked = True
                    break
            except requests.RequestException:
                continue

        if not health_checked:
            result['health'] = 'unreachable'
            result['health_message'] = 'No response from service'

        return result

    @staticmethod
    def get_all_service_statuses():
        """Get status of all configured services"""
        services = ServiceManager.get_all_services()
        statuses = {}

        for service_name in services:
            statuses[service_name] = ServiceManager.get_service_status(service_name)

        return statuses

    @staticmethod
    def get_service_logs(service_name, lines=100, log_type='stderr'):
        """
        Get recent logs for a service

        Args:
            service_name: Name of the service
            lines: Number of lines to retrieve (default 100)
            log_type: 'stdout', 'stderr', or 'both' (default 'stderr')

        Returns:
            dict with stdout and/or stderr content
        """
        stdout_path, stderr_path = ServiceManager.get_log_file_paths(service_name)

        result = {}

        def tail_file(filepath, num_lines):
            """Read last N lines from a file"""
            if not os.path.exists(filepath):
                return f"Log file not found: {filepath}"

            try:
                with open(filepath, 'r') as f:
                    content = f.readlines()
                    return ''.join(content[-num_lines:]) if content else "No logs available"
            except Exception as e:
                return f"Error reading log file: {str(e)}"

        if log_type in ('stdout', 'both'):
            result['stdout'] = tail_file(stdout_path, lines)

        if log_type in ('stderr', 'both'):
            result['stderr'] = tail_file(stderr_path, lines)

        return result

    @staticmethod
    def collect_metrics(service_name):
        """Collect and store metrics for a service"""
        status = ServiceStatus.query.filter_by(service_name=service_name).first()

        if not status or not status.pid:
            return

        proc_info = ServiceManager.get_process_info(status.pid)
        if not proc_info:
            return

        # Store metrics
        timestamp = datetime.utcnow()

        cpu_metric = ServiceMetric(
            service_name=service_name,
            timestamp=timestamp,
            metric_name='cpu_percent',
            metric_value=proc_info['cpu_percent']
        )

        memory_metric = ServiceMetric(
            service_name=service_name,
            timestamp=timestamp,
            metric_name='memory_mb',
            metric_value=proc_info['memory_mb']
        )

        db.session.add(cpu_metric)
        db.session.add(memory_metric)

        # Update service status
        status.cpu_percent = proc_info['cpu_percent']
        status.memory_mb = proc_info['memory_mb']
        status.last_checked = timestamp

        db.session.commit()
