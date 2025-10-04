-- Fix PostgreSQL permissions for helm_user
-- Run this with: sudo -u postgres psql -f fix_permissions.sql

\c helm_db

-- Grant schema permissions (required for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO helm_user;

-- Grant permissions on existing objects
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO helm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO helm_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO helm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO helm_user;

-- Verify permissions
\dp
