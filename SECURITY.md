# HiveMatrix Security Guide

## Overview

HiveMatrix follows a **zero-trust internal network model**. Only the Nexus gateway (port 443) should be accessible externally. All other services (Core, Keycloak, individual apps) should only listen on localhost and be accessed through the Nexus proxy.

## Architecture

```
Internet → Port 443 (Nexus with HTTPS)
                ↓
         [Nexus Proxy]
                ↓
    ┌───────────┼───────────┐
    ↓           ↓           ↓
Keycloak:8080 Core:5000  Apps:50XX
(localhost)  (localhost) (localhost)
```

## Security Audit

Run the security audit tool to check for exposed services:

```bash
cd hivematrix-helm
source pyenv/bin/activate
python security_audit.py --audit
```

This will check all services and report:
- ✓ Services properly bound to localhost
- ✗ Services exposed to all interfaces (security risk)
- ○ Services not running

## Firewall Configuration

### Ubuntu/Debian (UFW)

Generate and apply firewall rules:

```bash
cd hivematrix-helm
python security_audit.py --generate-firewall
sudo bash secure_firewall.sh
```

This will:
1. Enable UFW firewall
2. Allow SSH (port 22)
3. Allow HTTPS (port 443 - Nexus)
4. Block all HiveMatrix internal ports from external access

Verify firewall status:
```bash
sudo ufw status numbered
```

### Alternative: iptables

If you prefer iptables:

```bash
cd hivematrix-helm
python security_audit.py --generate-iptables
sudo bash secure_iptables.sh
```

## Service Binding Configuration

### Python Services (Core, Nexus, Apps)

All Python services use Flask's `app.run()` or similar WSGI servers. They should bind to `127.0.0.1`:

**Correct Configuration:**
```python
# Secure - localhost only
app.run(host='127.0.0.1', port=5040)
```

**Insecure Configuration:**
```python
# INSECURE - accessible from network
app.run(host='0.0.0.0', port=5040)
```

**Exception:** Nexus should bind to `0.0.0.0` on port 443 as it's the public entry point.

### Keycloak Configuration

Keycloak is a Java application with different configuration. The `start.sh` script configures Keycloak to listen on all interfaces by default, which is required for it to work properly in the proxied setup.

**Security for Keycloak:**
Keycloak (port 8080) should be protected by the firewall. The `start.sh` script automatically configures Keycloak with:

```ini
# In keycloak.conf
hostname-url=https://${HOSTNAME}/keycloak
hostname-admin-url=http://localhost:8080
hostname-strict=false
proxy-headers=xforwarded
http-enabled=true
```

This configuration:
- Sets the public URL to go through Nexus proxy
- Keeps admin interface on localhost:8080
- Accepts X-Forwarded headers from Nexus

**Important:** Always use the firewall to block external access to port 8080. Never expose Keycloak directly to the internet.

## Port Reference

### Public Ports (Externally Accessible)
- **443** - Nexus (HTTPS) - Main entry point

### Internal Ports (Localhost Only)
- **8080** - Keycloak - Authentication server
- **5000** - Core - Service registry & token management
- **5004** - Helm - Orchestration dashboard
- **5010** - Codex - MSP data hub
- **5020** - KnowledgeTree - Knowledge management
- **5030** - Ledger - Billing & invoicing
- **5040** - Template - Service template

### SSH Access
- **22** - SSH - Remote administration (firewall allows)

## Verification

After applying security fixes:

1. **Check Service Bindings:**
```bash
ss -tlnp | grep -E ":(8080|5000|5004|5010|5020|5030|5040|443)"
```

Expected output:
- Most services on `127.0.0.1:PORT`
- Only Nexus (443) on `0.0.0.0:443`

2. **Run Security Audit:**
```bash
python security_audit.py --audit
```

Expected: No exposed services (except Nexus on 443)

3. **Test External Access:**

From another machine on the network:
```bash
# Should work - Nexus on 443
curl -k https://YOUR_SERVER_IP:443

# Should fail - internal services blocked
curl http://YOUR_SERVER_IP:8080  # Keycloak - should timeout
curl http://YOUR_SERVER_IP:5000  # Core - should timeout
curl http://YOUR_SERVER_IP:5004  # Helm - should timeout
```

4. **Test Internal Access:**

From the server itself:
```bash
# Should work - services on localhost
curl http://localhost:8080
curl http://localhost:5000
curl http://localhost:5004
```

## Security Checklist

- [ ] Run `python security_audit.py --audit` - no exposed services
- [ ] Apply firewall rules (`sudo bash secure_firewall.sh`)
- [ ] Verify firewall status (`sudo ufw status`)
- [ ] Test external access blocked (from another machine)
- [ ] Test internal access works (from localhost)
- [ ] Ensure Nexus has valid SSL certificate
- [ ] Change default Keycloak admin password
- [ ] Change default HiveMatrix admin password
- [ ] Review Keycloak realm settings
- [ ] Enable Keycloak security features (brute force detection, etc.)

## Common Issues

### Issue: Service won't start after changing binding

**Symptom:** Service fails to start after changing from `0.0.0.0` to `127.0.0.1`

**Solution:** This usually means the service is working correctly. Test access:
```bash
curl http://localhost:PORT  # Should work
curl http://YOUR_IP:PORT    # Should fail (this is correct!)
```

### Issue: Nexus can't reach backend services

**Symptom:** Nexus returns 502 Bad Gateway

**Solution:** Backend services must listen on `127.0.0.1`, and Nexus connects to them via `http://localhost:PORT`. Check:
1. Services are running: `python cli.py status`
2. Services are on localhost: `ss -tlnp | grep PORT`
3. Nexus can connect: `curl http://localhost:PORT` from Nexus machine

### Issue: Locked out after applying firewall

**Symptom:** Can't SSH to server

**Solution:** This shouldn't happen as the firewall script allows SSH (port 22). If it does:
1. Access server console (physical or VM console)
2. Disable firewall: `sudo ufw disable`
3. Fix SSH rule: `sudo ufw allow 22/tcp`
4. Re-enable: `sudo ufw enable`

## Production Deployment

For production environments:

1. **Use proper SSL certificates** (not self-signed) for Nexus
2. **Configure hostname** in master_config.json to your domain/IP
3. **Run security audit** before going live
4. **Apply firewall rules** on the host
5. **Consider additional hardening:**
   - Fail2ban for SSH
   - Rate limiting on Nexus
   - Regular security updates
   - Monitoring and logging

## Additional Security Layers

### Fail2ban for SSH Protection

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Rate Limiting in Nexus

Nexus uses Gunicorn in production. Configure rate limiting in your reverse proxy or load balancer.

### Regular Updates

```bash
# System updates
sudo apt update && sudo apt upgrade

# HiveMatrix updates
cd hivematrix-helm
./start.sh  # Automatically pulls updates for services
```

## Reporting Security Issues

If you discover a security vulnerability in HiveMatrix:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to the maintainers
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

## References

- HiveMatrix Architecture: `ARCHITECTURE.md`
- UFW Documentation: https://help.ubuntu.com/community/UFW
- Keycloak Security: https://www.keycloak.org/docs/latest/server_admin/#_hardening
