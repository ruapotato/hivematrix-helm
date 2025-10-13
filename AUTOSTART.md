# HiveMatrix Auto-Start Guide

This guide explains how to configure HiveMatrix to start automatically on system boot.

## Security Review ✅

**Current Status:**
- ✅ All services run as user `david` (NOT root)
- ✅ Port 443 binding uses `cap_net_bind_service` capability (secure method)
- ✅ No sudo required for service operation
- ✅ Proper privilege separation

**Process ownership:**
```bash
$ ps aux | grep -E "(run.py|gunicorn|keycloak)" | grep -v grep
david     680199  ... java ... keycloak
david     680515  ... python run.py (core)
david     680544  ... gunicorn (nexus)
david     680592  ... python run.py (knowledgetree)
david     680668  ... python run.py (helm)
```

## Auto-Start Options

### Option 1: User Systemd Service (Recommended)

**Advantages:**
- No root privileges required for service operation
- Automatic restart on failure
- Centralized logging via journalctl
- Clean service management

**Prerequisites:**
⚠️ **IMPORTANT:** Run `./start.sh` ONCE manually before installing the systemd service!

This initial run will:
- Install system dependencies (PostgreSQL, Java, etc.) - needs sudo
- Set up port 443 binding capability - needs sudo
- Configure databases and Keycloak
- Test that everything works

**Installation:**
```bash
# Step 1: Initial setup (run once)
cd /home/david/Work/hivematrix/hivematrix-helm
./start.sh

# Wait for services to start, then press Ctrl+C to stop

# Step 2: Install systemd service
./install_autostart.sh
```

This will:
1. Install systemd user service
2. Enable auto-start on boot
3. Enable user linger (keeps services running without active login)

**Note:** You may need sudo for the linger step:
```bash
sudo loginctl enable-linger david
```

**Service Management:**
```bash
# Start services
systemctl --user start hivematrix

# Stop services
systemctl --user stop hivematrix

# Check status
systemctl --user status hivematrix

# View logs
journalctl --user -u hivematrix -f

# Disable auto-start
systemctl --user disable hivematrix
```

### Option 2: Cron @reboot

**Advantages:**
- Simple, no systemd knowledge required
- Works on all systems with cron

**Installation:**
```bash
crontab -e
```

Add this line:
```cron
@reboot cd /home/david/Work/hivematrix/hivematrix-helm && ./start.sh >> logs/cron.log 2>&1
```

**Limitations:**
- No automatic restart on failure
- Manual process management
- Less structured logging

### Option 3: System Systemd Service (Not Recommended)

**Why not recommended:**
- Requires running start.sh as root
- Less secure than user service
- More complex permission management

If you still want this approach:
```bash
sudo cp hivematrix.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hivematrix
sudo systemctl start hivematrix
```

## Troubleshooting

### Service fails to start

**Check logs:**
```bash
journalctl --user -u hivematrix -n 50
```

**Common issues:**
1. **PostgreSQL not running:**
   ```bash
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

2. **Port 443 permission denied:**
   ```bash
   # Check capability is set
   getcap /usr/bin/python3.12

   # Should show: cap_net_bind_service=ep
   # If not, run start.sh once manually to set it
   ```

3. **Virtual environment issues:**
   ```bash
   cd /home/david/Work/hivematrix/hivematrix-helm
   rm -rf pyenv
   python3 -m venv pyenv
   source pyenv/bin/activate
   pip install -r requirements.txt
   ```

### Service starts but web interface unreachable

**Check service status:**
```bash
cd /home/david/Work/hivematrix/hivematrix-helm
source pyenv/bin/activate
python cli.py status
```

**Check listening ports:**
```bash
ss -tlnp | grep -E "(443|5004|8080|5000)"
```

### Logs show authentication errors

Check that Core service is running and Keycloak is configured:
```bash
python cli.py status
# All services should show "running"
```

If Keycloak needs reconfiguration:
```bash
./configure_keycloak.sh
```

## Manual Start (Alternative)

If you prefer manual control, you can always start HiveMatrix manually:

```bash
cd /home/david/Work/hivematrix/hivematrix-helm
./start.sh
```

Press `Ctrl+C` to stop all services.

## Files

- `hivematrix.service` - Systemd service definition
- `systemd_start.sh` - Service startup script
- `systemd_stop.sh` - Service shutdown script
- `install_autostart.sh` - Auto-start installation script
- `start.sh` - Manual/interactive startup script

## Security Notes

1. **User Services vs System Services:**
   - User services run in user context (secure)
   - System services typically run as root (less secure)
   - HiveMatrix uses user services by default

2. **Port 443 Binding:**
   - Uses Linux capabilities instead of root
   - `cap_net_bind_service` allows binding privileged ports
   - Applied to system Python binary, not per-user

3. **Service Isolation:**
   - Each service runs in its own Python virtualenv
   - Database credentials stored per-service
   - JWT keys isolated to Core service

## Monitoring

**Check all services:**
```bash
systemctl --user status hivematrix
```

**Real-time logs:**
```bash
journalctl --user -u hivematrix -f
```

**Check resource usage:**
```bash
# CPU and memory
ps aux | grep -E "(run.py|gunicorn|keycloak)"

# Network connections
ss -tlnp | grep -E "(443|5004|8080|5000|5020)"
```

## Uninstalling Auto-Start

**Remove systemd service:**
```bash
systemctl --user stop hivematrix
systemctl --user disable hivematrix
rm ~/.config/systemd/user/hivematrix.service
systemctl --user daemon-reload
```

**Remove cron job:**
```bash
crontab -e
# Delete the @reboot line
```

**Disable linger (optional):**
```bash
sudo loginctl disable-linger david
```
