#!/bin/bash
#
# HiveMatrix Security - UFW Firewall Rules
# This script configures Ubuntu's firewall to secure HiveMatrix services
#

echo '================================================'
echo '  HiveMatrix Firewall Configuration'
echo '================================================'
echo ''

# Enable UFW if not already enabled
sudo ufw --force enable
echo 'UFW enabled'

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing
echo 'Default policies set'

# Allow SSH (IMPORTANT: Don't lock yourself out!)
sudo ufw allow 22/tcp comment 'SSH access'
echo 'SSH access allowed on port 22'

# Allow HTTPS (Nexus - main entry point)
sudo ufw allow 443/tcp comment 'HiveMatrix Nexus (HTTPS)'
echo 'HTTPS access allowed on port 443 (Nexus)'

# DENY all other HiveMatrix internal ports from external access
# These services should ONLY be accessible via localhost

# Block external access to codex
sudo ufw deny 5010/tcp comment 'Block external codex'
echo 'Port 5010 (codex) blocked from external access'

# Block external access to core
sudo ufw deny 5000/tcp comment 'Block external core'
echo 'Port 5000 (core) blocked from external access'

# Block external access to helm
sudo ufw deny 5004/tcp comment 'Block external helm'
echo 'Port 5004 (helm) blocked from external access'

# Block external access to keycloak
sudo ufw deny 8080/tcp comment 'Block external keycloak'
echo 'Port 8080 (keycloak) blocked from external access'

# Block external access to knowledgetree
sudo ufw deny 5020/tcp comment 'Block external knowledgetree'
echo 'Port 5020 (knowledgetree) blocked from external access'

# Block external access to ledger
sudo ufw deny 5030/tcp comment 'Block external ledger'
echo 'Port 5030 (ledger) blocked from external access'

# Block external access to template
sudo ufw deny 5040/tcp comment 'Block external template'
echo 'Port 5040 (template) blocked from external access'

# Show status
echo ''
echo '================================================'
echo '  Firewall Configuration Complete'
echo '================================================'
sudo ufw status numbered
echo ''
echo 'Only ports 22 (SSH) and 443 (HTTPS) are accessible externally.'
echo 'All HiveMatrix services are protected and only accessible via Nexus proxy.'

