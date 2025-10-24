#!/usr/bin/env python3
"""
Add Archive service to both master_services.json and services.json
"""

import json

# Add to master_services.json
print("Updating master_services.json...")
with open('master_services.json', 'r') as f:
    master_services = json.load(f)

if 'archive' not in master_services:
    master_services['archive'] = {
        "url": "http://localhost:5012",
        "port": 5012
    }

    with open('master_services.json', 'w') as f:
        json.dump(master_services, f, indent=2)
    print("✓ Added archive to master_services.json")
else:
    print("✓ archive already in master_services.json")

# Add to services.json
print("\nUpdating services.json...")
with open('services.json', 'r') as f:
    services = json.load(f)

if 'archive' not in services:
    services['archive'] = {
        "url": "http://localhost:5012",
        "path": "../hivematrix-archive",
        "port": 5012,
        "python_bin": "pyenv/bin/python",
        "run_script": "run.py",
        "visible": True
    }

    with open('services.json', 'w') as f:
        json.dump(services, f, indent=2)
    print("✓ Added archive to services.json")
else:
    print("✓ archive already in services.json")

print("\n✅ Archive service configuration complete!")
print("\nYou can now start Archive with:")
print("  python cli.py start archive")
print("\nOr restart start.sh to auto-start all services")
