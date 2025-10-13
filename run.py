from app import app
from app.service_manager import ServiceManager
import requests
import sys
import time

def check_required_services():
    """Check if required services (Keycloak, Core, Nexus) are running"""
    print("\n" + "="*60)
    print("HiveMatrix Helm - Service Orchestration & Monitoring")
    print("="*60)

    services = app.config.get('SERVICES', {})

    # Check Keycloak
    keycloak_config = services.get('keycloak')
    core_config = services.get('core')
    nexus_config = services.get('nexus')

    all_running = True

    if keycloak_config:
        print(f"\nChecking Keycloak at {keycloak_config['url']}...")
        keycloak_healthy = False
        # Retry up to 5 times (15 seconds total)
        for attempt in range(5):
            try:
                response = requests.get(f"{keycloak_config['url']}", timeout=3)
                print("✓ Keycloak is running")
                keycloak_healthy = True
                break
            except requests.RequestException:
                if attempt < 4:  # Don't sleep on last attempt
                    if attempt == 0:
                        print("  Waiting for Keycloak to be ready...")
                    time.sleep(3)

        if not keycloak_healthy:
            print("✗ Keycloak is NOT running after 15s")
            all_running = False

    if core_config:
        print(f"\nChecking Core service at {core_config['url']}...")
        core_healthy = False
        # Retry up to 5 times (15 seconds total)
        for attempt in range(5):
            # Try /health first, fall back to /
            for endpoint in ['/health', '/']:
                try:
                    response = requests.get(f"{core_config['url']}{endpoint}", timeout=3)
                    if response.status_code == 200:
                        print(f"✓ Core service is running (checked {endpoint})")
                        core_healthy = True
                        break
                except requests.RequestException:
                    continue

            if core_healthy:
                break

            if attempt < 4:  # Don't sleep on last attempt
                if attempt == 0:
                    print("  Waiting for Core to be ready...")
                time.sleep(3)

        if not core_healthy:
            print("✗ Core service is NOT running after 15s")
            all_running = False

    if nexus_config:
        print(f"\nChecking Nexus service at {nexus_config['url']}/health...")
        nexus_healthy = False
        # Disable SSL verification for self-signed certificates
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Retry up to 10 times (30 seconds total) - Nexus can take time to bind to port 443
        for attempt in range(10):
            try:
                response = requests.get(f"{nexus_config['url']}/health", timeout=3, verify=False)
                if response.status_code == 200:
                    print("✓ Nexus service is running")
                    nexus_healthy = True
                    break
            except requests.RequestException as e:
                if attempt < 9:  # Don't sleep on last attempt
                    if attempt == 0:
                        print("  Waiting for Nexus to be ready...")
                    time.sleep(3)
                else:
                    print(f"✗ Nexus service is NOT running after 30s: {e}")

        if not nexus_healthy:
            all_running = False

    print("\n" + "-"*60)

    if not all_running:
        print("\n⚠️  REQUIRED SERVICES NOT RUNNING")
        print("\nHelm requires Keycloak, Core, and Nexus to be running")
        print("for authentication and web interface access.")
        print("\nYou can use the CLI to start services:")
        print("  python cli.py start keycloak")
        print("  python cli.py start core")
        print("  python cli.py start nexus")
        print("\nOr start them manually and restart Helm.")
        print("-"*60 + "\n")
        return False

    print("✓ All required services are running")
    print("\nHelm Dashboard: http://localhost:5004")
    print("Health Check:   http://localhost:5004/health")
    print("-"*60 + "\n")
    return True

if __name__ == '__main__':
    if not check_required_services():
        print("Exiting: Required services not available")
        print("Start required services first, then restart Helm.\n")
        sys.exit(1)

    # Security: Bind to localhost only - Helm should not be exposed externally
    # Access via Nexus proxy at https://localhost:443/helm
    app.run(host='127.0.0.1', port=5004, debug=True)
