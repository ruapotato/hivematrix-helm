#!/usr/bin/env python3
"""
HiveMatrix Helm - Security Audit Module
Checks for exposed ports and provides security recommendations
"""

import socket
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple

class SecurityAuditor:
    """Audits HiveMatrix security configuration"""

    # Services that should ONLY be accessible on localhost
    LOCALHOST_ONLY_SERVICES = {
        'core': 5000,
        'helm': 5004,
        'codex': 5010,
        'ledger': 5030,
        'template': 5040,
        'knowledgetree': 5020,
    }

    # Services that can be exposed but MUST be protected by firewall
    # These services may bind to 0.0.0.0 (Java apps, etc.) but external access
    # should be blocked by firewall rules
    FIREWALL_PROTECTED_SERVICES = {
        'keycloak': 8080,  # Java app, binds to 0.0.0.0, block with firewall
    }

    # Services that should be accessible on all interfaces
    PUBLIC_SERVICES = {
        'nexus': 443,  # Main entry point with HTTPS
    }

    def __init__(self, helm_dir: str = None):
        self.helm_dir = Path(helm_dir) if helm_dir else Path(__file__).parent
        self.parent_dir = self.helm_dir.parent

    def check_port_binding(self, port: int) -> Tuple[bool, str]:
        """
        Check if a port is bound to localhost or all interfaces
        Returns: (is_localhost_only, binding_address)
        """
        try:
            # Use ss command to check port bindings
            result = subprocess.run(
                ['ss', '-tlnp'],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.split('\n'):
                if f':{port}' in line:
                    # Parse the line to get the binding address
                    parts = line.split()
                    if len(parts) >= 4:
                        local_addr = parts[3]
                        # Extract just the IP part
                        if ':' in local_addr:
                            ip = local_addr.rsplit(':', 1)[0]
                            # Handle IPv6 addresses
                            if ip == '[::]' or ip == '*':
                                return False, '0.0.0.0'
                            elif ip == '127.0.0.1' or ip == '[::1]':
                                return True, '127.0.0.1'
                            elif ip == '0.0.0.0':
                                return False, '0.0.0.0'
                            else:
                                return False, ip

            # Port not found - not listening
            return None, 'not listening'

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None, 'unknown'

    def audit_services(self) -> Dict:
        """
        Audit all HiveMatrix services for security issues
        Returns dict with findings
        """
        findings = {
            'exposed_services': [],
            'secure_services': [],
            'firewall_required': [],
            'not_running': [],
            'unknown_services': [],
            'severity': 'none'  # none, low, medium, high, critical
        }

        # Check localhost-only services
        for service_name, port in self.LOCALHOST_ONLY_SERVICES.items():
            is_localhost, binding = self.check_port_binding(port)

            if is_localhost is None:
                findings['not_running'].append({
                    'service': service_name,
                    'port': port,
                    'status': 'not running'
                })
            elif is_localhost:
                findings['secure_services'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'secure'
                })
            else:
                findings['exposed_services'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'EXPOSED',
                    'severity': 'high',
                    'issue': f'{service_name} is listening on {binding} (should be 127.0.0.1 only)'
                })

        # Check firewall-protected services (can be exposed if firewalled)
        for service_name, port in self.FIREWALL_PROTECTED_SERVICES.items():
            is_localhost, binding = self.check_port_binding(port)

            if is_localhost is None:
                findings['not_running'].append({
                    'service': service_name,
                    'port': port,
                    'status': 'not running'
                })
            elif is_localhost:
                findings['secure_services'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'secure (localhost)'
                })
            else:
                # Exposed but acceptable if firewalled
                findings['firewall_required'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'NEEDS FIREWALL',
                    'severity': 'medium',
                    'issue': f'{service_name} is listening on {binding} - must be protected by firewall'
                })

        # Check public services
        for service_name, port in self.PUBLIC_SERVICES.items():
            is_localhost, binding = self.check_port_binding(port)

            if is_localhost is None:
                findings['not_running'].append({
                    'service': service_name,
                    'port': port,
                    'status': 'not running'
                })
            elif is_localhost:
                # Nexus on localhost is a warning - it should be on 0.0.0.0
                findings['unknown_services'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'WARNING',
                    'severity': 'low',
                    'issue': f'{service_name} is only on localhost, should be accessible externally'
                })
            else:
                findings['secure_services'].append({
                    'service': service_name,
                    'port': port,
                    'binding': binding,
                    'status': 'correct (public)'
                })

        # Determine overall severity
        if findings['exposed_services']:
            findings['severity'] = 'high'
        elif findings['firewall_required']:
            findings['severity'] = 'medium'
        elif findings['unknown_services']:
            findings['severity'] = 'low'

        return findings

    def generate_firewall_rules(self, detected_ip: str = None) -> str:
        """
        Generate Ubuntu/ufw firewall rules to lock down services
        """
        rules = []
        rules.append("#!/bin/bash")
        rules.append("#")
        rules.append("# HiveMatrix Security - UFW Firewall Rules")
        rules.append("# This script configures Ubuntu's firewall to secure HiveMatrix services")
        rules.append("#")
        rules.append("")
        rules.append("echo '================================================'")
        rules.append("echo '  HiveMatrix Firewall Configuration'")
        rules.append("echo '================================================'")
        rules.append("echo ''")
        rules.append("")
        rules.append("# Enable UFW if not already enabled")
        rules.append("sudo ufw --force enable")
        rules.append("echo 'UFW enabled'")
        rules.append("")
        rules.append("# Set default policies")
        rules.append("sudo ufw default deny incoming")
        rules.append("sudo ufw default allow outgoing")
        rules.append("echo 'Default policies set'")
        rules.append("")
        rules.append("# Allow SSH (IMPORTANT: Don't lock yourself out!)")
        rules.append("sudo ufw allow 22/tcp comment 'SSH access'")
        rules.append("echo 'SSH access allowed on port 22'")
        rules.append("")
        rules.append("# Allow HTTPS (Nexus - main entry point)")
        rules.append("sudo ufw allow 443/tcp comment 'HiveMatrix Nexus (HTTPS)'")
        rules.append("echo 'HTTPS access allowed on port 443 (Nexus)'")
        rules.append("")
        rules.append("# DENY all other HiveMatrix internal ports from external access")
        rules.append("# These services should ONLY be accessible via localhost")
        rules.append("")

        for service_name, port in sorted(self.LOCALHOST_ONLY_SERVICES.items()):
            rules.append(f"# Block external access to {service_name}")
            rules.append(f"sudo ufw deny {port}/tcp comment 'Block external {service_name}'")
            rules.append(f"echo 'Port {port} ({service_name}) blocked from external access'")
            rules.append("")

        rules.append("# Show status")
        rules.append("echo ''")
        rules.append("echo '================================================'")
        rules.append("echo '  Firewall Configuration Complete'")
        rules.append("echo '================================================'")
        rules.append("sudo ufw status numbered")
        rules.append("echo ''")
        rules.append("echo 'Only ports 22 (SSH) and 443 (HTTPS) are accessible externally.'")
        rules.append("echo 'All HiveMatrix services are protected and only accessible via Nexus proxy.'")
        rules.append("")

        return '\n'.join(rules) + '\n'

    def generate_iptables_rules(self) -> str:
        """
        Generate iptables rules (alternative to ufw)
        """
        rules = []
        rules.append("#!/bin/bash")
        rules.append("#")
        rules.append("# HiveMatrix Security - iptables Rules")
        rules.append("# Alternative firewall configuration using iptables")
        rules.append("#")
        rules.append("")
        rules.append("# Flush existing rules")
        rules.append("sudo iptables -F")
        rules.append("sudo iptables -X")
        rules.append("")
        rules.append("# Set default policies")
        rules.append("sudo iptables -P INPUT DROP")
        rules.append("sudo iptables -P FORWARD DROP")
        rules.append("sudo iptables -P OUTPUT ACCEPT")
        rules.append("")
        rules.append("# Allow loopback")
        rules.append("sudo iptables -A INPUT -i lo -j ACCEPT")
        rules.append("")
        rules.append("# Allow established connections")
        rules.append("sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT")
        rules.append("")
        rules.append("# Allow SSH")
        rules.append("sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT")
        rules.append("")
        rules.append("# Allow HTTPS (Nexus)")
        rules.append("sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT")
        rules.append("")
        rules.append("# All other ports are blocked by default DROP policy")
        rules.append("")
        rules.append("# Save rules")
        rules.append("sudo iptables-save | sudo tee /etc/iptables/rules.v4")
        rules.append("")
        rules.append("echo 'iptables rules configured and saved'")
        rules.append("")

        return '\n'.join(rules) + '\n'

    def print_report(self, findings: Dict):
        """Print a formatted security audit report"""
        print("\n" + "="*80)
        print("  HiveMatrix Security Audit Report")
        print("="*80 + "\n")

        # Summary
        total_checked = (len(findings['exposed_services']) +
                        len(findings['secure_services']) +
                        len(findings['firewall_required']) +
                        len(findings['not_running']) +
                        len(findings['unknown_services']))

        print(f"Services Checked: {total_checked}")
        print(f"Overall Severity: {findings['severity'].upper()}")
        print("")

        # Exposed services (CRITICAL)
        if findings['exposed_services']:
            print("🔴 EXPOSED SERVICES (HIGH RISK)")
            print("-" * 80)
            for svc in findings['exposed_services']:
                print(f"  ✗ {svc['service'].upper():15} Port {svc['port']:5} → {svc['binding']}")
                print(f"    Issue: {svc['issue']}")
            print("")

        # Firewall-required services
        if findings['firewall_required']:
            print("⚠ FIREWALL PROTECTION REQUIRED")
            print("-" * 80)
            for svc in findings['firewall_required']:
                print(f"  ⚠ {svc['service'].upper():15} Port {svc['port']:5} → {svc['binding']}")
                print(f"    Status: {svc['status']} - {svc['issue']}")
            print("")

        # Secure services
        if findings['secure_services']:
            print("✓ SECURE SERVICES")
            print("-" * 80)
            for svc in findings['secure_services']:
                print(f"  ✓ {svc['service']:15} Port {svc['port']:5} → {svc['binding']} ({svc['status']})")
            print("")

        # Not running
        if findings['not_running']:
            print("ℹ NOT RUNNING")
            print("-" * 80)
            for svc in findings['not_running']:
                print(f"  ○ {svc['service']:15} Port {svc['port']:5} (not listening)")
            print("")

        # Warnings
        if findings['unknown_services']:
            print("⚠ WARNINGS")
            print("-" * 80)
            for svc in findings['unknown_services']:
                print(f"  ⚠ {svc['service'].upper():15} Port {svc['port']:5} → {svc['binding']}")
                print(f"    Issue: {svc['issue']}")
            print("")

        # Recommendations
        if findings['exposed_services']:
            print("="*80)
            print("  CRITICAL: SECURITY ACTION REQUIRED")
            print("="*80 + "\n")
            print("❗ Some services are exposed to the network without protection!")
            print("")
            print("1. Fix Service Bindings:")
            print("   - Update run.py files to bind to '127.0.0.1' instead of '0.0.0.0'")
            print("   - Restart the affected services")
            print("")
            print("2. Configure Firewall:")
            print("   - Run: python security_audit.py --generate-firewall")
            print("   - Execute the generated script: sudo bash secure_firewall.sh")
            print("")
            print("3. Verify:")
            print("   - Run: python security_audit.py --audit")
            print("   - Check that only Nexus (port 443) is externally accessible")
            print("")
        elif findings['firewall_required']:
            print("="*80)
            print("  RECOMMENDED: APPLY FIREWALL PROTECTION")
            print("="*80 + "\n")
            print("⚠️  Some services can accept external connections.")
            print("   This is acceptable for Java applications like Keycloak,")
            print("   but you MUST configure firewall to block external access.")
            print("")
            print("Apply Firewall Protection:")
            print("   1. Generate: python security_audit.py --generate-firewall")
            print("   2. Review the script: cat secure_firewall.sh")
            print("   3. Apply: sudo bash secure_firewall.sh")
            print("")
            print("After applying firewall:")
            print("   - External access to internal ports will be blocked")
            print("   - Only ports 22 (SSH) and 443 (HTTPS) will be accessible")
            print("   - Run audit again to verify: python security_audit.py --audit")
            print("")
        elif findings['severity'] == 'none':
            print("="*80)
            print("✓ All services are properly configured!")
            print("="*80 + "\n")

        print("="*80 + "\n")


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='HiveMatrix Security Audit Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --audit                  # Run security audit
  %(prog)s --generate-firewall      # Generate UFW firewall script
  %(prog)s --generate-iptables      # Generate iptables script
  %(prog)s --json                   # Output audit results as JSON
        """
    )

    parser.add_argument('--audit', action='store_true',
                       help='Run security audit')
    parser.add_argument('--generate-firewall', action='store_true',
                       help='Generate UFW firewall configuration script')
    parser.add_argument('--generate-iptables', action='store_true',
                       help='Generate iptables configuration script')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')

    args = parser.parse_args()

    auditor = SecurityAuditor()

    if args.generate_firewall:
        script = auditor.generate_firewall_rules()
        output_file = Path(__file__).parent / 'secure_firewall.sh'
        with open(output_file, 'w') as f:
            f.write(script)
        # Make executable
        output_file.chmod(0o755)
        print(f"✓ Firewall script generated: {output_file}")
        print(f"\nTo apply firewall rules, run:")
        print(f"  sudo bash {output_file}")
        print(f"\nWARNING: Make sure you have SSH access before applying!")

    elif args.generate_iptables:
        script = auditor.generate_iptables_rules()
        output_file = Path(__file__).parent / 'secure_iptables.sh'
        with open(output_file, 'w') as f:
            f.write(script)
        output_file.chmod(0o755)
        print(f"✓ iptables script generated: {output_file}")
        print(f"\nTo apply iptables rules, run:")
        print(f"  sudo bash {output_file}")

    elif args.audit or not any(vars(args).values()):
        # Default action is audit
        findings = auditor.audit_services()

        if args.json:
            print(json.dumps(findings, indent=2))
        else:
            auditor.print_report(findings)

        # Exit with error code if there are exposed services
        if findings['exposed_services']:
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
