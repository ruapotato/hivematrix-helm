#!/usr/bin/env python3
"""
HiveMatrix Helm CLI
Command-line interface for managing services
"""

import sys
import argparse
from app import app
from app.service_manager import ServiceManager

def status_command(args):
    """Show status of all services"""
    with app.app_context():
        statuses = ServiceManager.get_all_service_statuses()

        print("\n" + "="*80)
        print("HiveMatrix Service Status")
        print("="*80)

        for service_name, status in statuses.items():
            state = status.get('status', 'unknown')
            health = status.get('health', 'unknown')
            pid = status.get('pid', '-')
            port = status.get('configured_port', '-')

            print(f"\n{service_name.upper()}")
            print(f"  Status:  {state}")
            print(f"  Health:  {health}")
            print(f"  Port:    {port}")
            print(f"  PID:     {pid}")

        print("\n" + "="*80 + "\n")

def start_command(args):
    """Start a service"""
    with app.app_context():
        result = ServiceManager.start_service(args.service, args.mode)

        if result['success']:
            print(f"✓ {result['message']}")
            print(f"  PID: {result.get('pid')}")
            print(f"  Port: {result.get('port')}")
        else:
            print(f"✗ {result['message']}")
            sys.exit(1)

def stop_command(args):
    """Stop a service"""
    with app.app_context():
        result = ServiceManager.stop_service(args.service)

        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result['message']}")
            sys.exit(1)

def restart_command(args):
    """Restart a service"""
    with app.app_context():
        result = ServiceManager.restart_service(args.service, args.mode)

        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result['message']}")
            sys.exit(1)

def list_command(args):
    """List all configured services"""
    with app.app_context():
        services = ServiceManager.get_all_services()

        print("\nConfigured Services:")
        print("-" * 40)
        for name, config in services.items():
            service_type = config.get('type', 'python')
            port = config.get('port', 'N/A')
            print(f"  {name:15} (type: {service_type:10} port: {port})")
        print()

def main():
    parser = argparse.ArgumentParser(
        description='HiveMatrix Helm CLI - Service Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    # Show all service statuses
  %(prog)s list                      # List configured services
  %(prog)s start keycloak            # Start Keycloak
  %(prog)s start core                # Start Core service
  %(prog)s stop nexus                # Stop Nexus service
  %(prog)s restart core --mode prod  # Restart Core in production mode
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Status command
    subparsers.add_parser('status', help='Show status of all services')

    # List command
    subparsers.add_parser('list', help='List all configured services')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start a service')
    start_parser.add_argument('service', help='Service name')
    start_parser.add_argument('--mode', choices=['development', 'production'],
                             default='development', help='Run mode (default: development)')

    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop a service')
    stop_parser.add_argument('service', help='Service name')

    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart a service')
    restart_parser.add_argument('service', help='Service name')
    restart_parser.add_argument('--mode', choices=['development', 'production'],
                               default='development', help='Run mode (default: development)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate command
    commands = {
        'status': status_command,
        'list': list_command,
        'start': start_command,
        'stop': stop_command,
        'restart': restart_command
    }

    commands[args.command](args)

if __name__ == '__main__':
    main()
