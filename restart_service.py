#!/usr/bin/env python3
"""
Quick service restart utility
Usage: python restart_service.py <service_name>
"""
import sys
from app.service_manager import ServiceManager
from app import app

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python restart_service.py <service_name>")
        print("Example: python restart_service.py knowledgetree")
        sys.exit(1)

    service_name = sys.argv[1]

    with app.app_context():
        print(f"Stopping {service_name}...")
        stop_result = ServiceManager.stop_service(service_name)
        print(stop_result)

        print(f"\nStarting {service_name}...")
        start_result = ServiceManager.start_service(service_name, mode='development')
        print(start_result)

        if start_result.get('success'):
            print(f"\n✓ {service_name} restarted successfully on port {start_result.get('port')}")
        else:
            print(f"\n✗ Failed to restart {service_name}")
            sys.exit(1)
