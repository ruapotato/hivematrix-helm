# HiveMatrix Refactor - Deployment Checklist

## Files Created in hivematrix-helm

### Core System Files
- [x] `apps_registry.json` - Registry of all available apps and dependencies
- [x] `install_manager.py` - App installation and git management
- [x] `config_manager.py` - Centralized configuration management
- [x] `start.sh.new` - New unified startup script with fresh install detection
- [x] `templates/install.sh` - Template for app install scripts

### API and Routes
- [x] `app/app_manager_routes.py` - API endpoints for app management
- [x] `app/routes.py` - Added /apps route
- [x] `app/__init__.py` - Import app_manager_routes

### Web UI
- [x] `app/templates/apps.html` - App management interface

### Documentation
- [x] `REFACTOR_SUMMARY.md` - Complete refactor documentation
- [x] `QUICK_START.md` - Quick start guide for fresh installs
- [x] `DEPLOYMENT_CHECKLIST.md` - This file

## Repository Updates Needed

### hivematrix-helm (This Repository)

1. **Test the new start.sh:**
   ```bash
   cd /home/david/work/hivematrix-helm

   # Backup current start.sh
   cp start.sh start.sh.backup

   # Replace with new version
   mv start.sh.new start.sh
   chmod +x start.sh
   ```

2. **Test fresh installation:**
   - Spin up Ubuntu 24.04 VM/container
   - Clone helm only
   - Run `./start.sh`
   - Verify all components install automatically

3. **Commit and push changes:**
   ```bash
   git add .
   git status
   # Review changes
   git commit -m "Major refactor: Unified orchestration system

   - App registry with installation manager
   - Centralized configuration management
   - Fresh install detection with auto-setup
   - Web-based app installation UI
   - Git operations for all modules
   - Dependency management
   - One-command installation on Ubuntu 24.04

   See REFACTOR_SUMMARY.md for details"

   git push origin main
   ```

### hivematrix-core

1. **Add install.sh:**
   ```bash
   cd /home/david/work/hivematrix-core

   # Copy template
   cp ../hivematrix-helm/templates/install.sh ./install.sh

   # Customize for Core
   sed -i 's/__APP_NAME__/core/g' install.sh
   ```

2. **Add Core-specific setup to install.sh:**
   ```bash
   # Between __CUSTOM_SETUP_START__ and __CUSTOM_SETUP_END__, add:
   # - Database initialization
   # - Keycloak client configuration
   # - Default .flaskenv creation
   ```

3. **Update README.md:**
   - Add note about Helm-based installation
   - Keep manual installation instructions as alternative
   - Link to QUICK_START.md in helm repo

4. **Commit and push:**
   ```bash
   git add install.sh
   git commit -m "Add install script for Helm orchestration"
   git push origin main
   ```

### hivematrix-nexus

1. **Add install.sh** (same process as Core)
2. **Customize for Nexus**
3. **Update README.md**
4. **Commit and push**

### hivematrix-codex

1. **Add install.sh:**
   ```bash
   cd /home/david/work/hivematrix-codex
   cp ../hivematrix-helm/templates/install.sh ./install.sh
   sed -i 's/__APP_NAME__/codex/g' install.sh
   ```

2. **Add Codex-specific setup:**
   ```bash
   # In install.sh between __CUSTOM_SETUP_START__ and __CUSTOM_SETUP_END__:

   # Setup PostgreSQL database
   echo "Setting up PostgreSQL database..."
   cd ../hivematrix-helm
   python config_manager.py setup-db codex
   cd - > /dev/null

   # Initialize database schema
   if [ -f "init_db.py" ]; then
       python pyenv/bin/python init_db.py
   fi

   # Create default configuration
   echo "Syncing configuration from Helm..."
   cd ../hivematrix-helm
   python config_manager.py write-dotenv codex
   python config_manager.py write-conf codex
   cd - > /dev/null
   ```

3. **Update README.md**
4. **Commit and push**

### hivematrix-ledger

1. **Add install.sh** (similar to Codex)
2. **Add Ledger-specific setup:**
   - PostgreSQL database for billing data
   - Configuration sync from Helm
3. **Update README.md**
4. **Commit and push**

### hivematrix-knowledgetree

1. **Add install.sh** (similar to Codex)
2. **Add KnowledgeTree-specific setup:**
   - Neo4j database setup (if installed)
   - Configuration sync from Helm
   - Note about Neo4j requirement
3. **Update README.md**
4. **Commit and push**

## Testing Checklist

### Fresh Installation Test

- [ ] Spin up fresh Ubuntu 24.04 VM
- [ ] Clone only hivematrix-helm
- [ ] Run `./start.sh`
- [ ] Verify it installs:
  - [ ] Python, Git, Java, PostgreSQL
  - [ ] Keycloak 26.0.5
  - [ ] Core and Nexus
- [ ] Verify it starts all services
- [ ] Verify login at http://localhost:8000 works
- [ ] Verify default credentials work (admin/admin)

### App Installation Test

- [ ] Navigate to http://localhost:5004/apps
- [ ] Verify available apps are listed
- [ ] Click "Install" on Codex
- [ ] Verify installation completes
- [ ] Verify Codex appears in installed apps
- [ ] Start Codex from main dashboard
- [ ] Verify Codex is accessible

### Git Operations Test

- [ ] Make a dummy commit in Codex repository
- [ ] Push to remote
- [ ] In /apps page, verify "Updates" shows commits behind
- [ ] Click "Update" button
- [ ] Verify git pull succeeds
- [ ] Verify app restarts

### Configuration Management Test

- [ ] Use config_manager.py to set Codex API keys
- [ ] Verify .flaskenv is updated
- [ ] Verify instance/codex.conf is updated
- [ ] Restart Codex
- [ ] Verify configuration is loaded

### Custom Git Install Test

- [ ] Go to /apps page
- [ ] Click "Install from Git" tab
- [ ] Enter a test repository URL
- [ ] Verify installation works
- [ ] Verify app appears in services

## Migration Guide for Existing Users

For users who already have HiveMatrix installed:

1. **Backup everything:**
   ```bash
   cd /home/david/work
   tar -czf hivematrix-backup-$(date +%Y%m%d).tar.gz hivematrix-* keycloak-*
   ```

2. **Update Helm:**
   ```bash
   cd hivematrix-helm
   git pull origin main
   ```

3. **Update service registry:**
   ```bash
   python install_manager.py update-config
   ```

4. **Sync configurations:**
   ```bash
   python config_manager.py sync-all
   ```

5. **Add install.sh to each app:**
   ```bash
   # For each app repository, pull the latest changes
   cd ../hivematrix-core && git pull
   cd ../hivematrix-nexus && git pull
   cd ../hivematrix-codex && git pull
   # etc.
   ```

6. **Restart using new start.sh:**
   ```bash
   cd ../hivematrix-helm
   ./start.sh
   ```

## Production Deployment

Before deploying to production:

- [ ] Change all default passwords
- [ ] Setup PostgreSQL with strong passwords
- [ ] Configure firewall (ufw)
- [ ] Setup Nginx reverse proxy
- [ ] Enable SSL/TLS with Let's Encrypt
- [ ] Configure systemd services
- [ ] Setup automated backups
- [ ] Configure log rotation
- [ ] Test disaster recovery

## Documentation Updates

- [ ] Update main README.md with new installation instructions
- [ ] Add QUICK_START.md to all repositories
- [ ] Update ARCHITECTURE.md with new orchestration flow
- [ ] Create video walkthrough (optional)
- [ ] Update screenshots in documentation

## Communication Plan

1. **Create announcement post:**
   - Explain the refactor
   - Highlight benefits
   - Link to QUICK_START.md
   - Provide migration guide

2. **Update GitHub:**
   - Create release tag
   - Write release notes
   - Pin announcement issue

3. **Support:**
   - Monitor GitHub issues
   - Provide migration assistance
   - Document common problems

## Future Enhancements

After initial deployment is stable:

- [ ] Docker support
- [ ] Backup/restore functionality
- [ ] Health checks before installation
- [ ] Rollback capability
- [ ] Multi-environment support (dev/staging/prod)
- [ ] App removal functionality
- [ ] Dependency auto-resolution
- [ ] Configuration validation
- [ ] Secrets management (encrypted API keys)
- [ ] Automated testing before deployment

## Known Issues

Document any known issues here:

1. **Neo4j Installation:**
   - Manual setup still required
   - Need to add automated installer

2. **Port Conflicts:**
   - If ports are already in use, installation may fail
   - Need better port conflict detection

3. **Database Permissions:**
   - PostgreSQL permissions may need manual adjustment on some systems
   - Need to add automatic permission grant

## Success Criteria

The refactor is successful when:

- [ ] A user can install HiveMatrix on fresh Ubuntu 24.04 with one command
- [ ] All default apps can be installed from web UI
- [ ] Git operations work for all modules
- [ ] Configuration is centralized and synced
- [ ] Existing users can migrate without data loss
- [ ] Documentation is complete and accurate
- [ ] No critical bugs in fresh installation
- [ ] Performance is equal to or better than before

## Sign-off

- [ ] Developer testing complete
- [ ] Documentation reviewed
- [ ] Migration guide tested
- [ ] Fresh install tested on Ubuntu 24.04
- [ ] Ready for production deployment

---

**Last Updated:** 2025-10-04
**Status:** Implementation Complete - Ready for Testing
