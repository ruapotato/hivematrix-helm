#!/usr/bin/env python3
"""
Quick CLI tool to view service logs from Helm database
Usage: python logs_cli.py [service_name] [--tail N] [--level LEVEL]
"""
import sys
import os
import configparser

# Get database connection from config
INSTANCE_PATH = os.path.join(os.path.dirname(__file__), 'instance')
CONFIG_PATH = os.path.join(INSTANCE_PATH, 'helm.conf')

def get_db_connection():
    """Get PostgreSQL connection string from config"""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Config not found at {CONFIG_PATH}")
        print("Run: python init_db.py")
        return None

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)

    try:
        return config.get('database', 'connection_string')
    except:
        print("❌ Database config not found in helm.conf")
        return None

def view_logs(service_name=None, tail=50, level=None):
    """View logs from database"""
    conn_str = get_db_connection()
    if not conn_str:
        return

    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        return

    try:
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        # Build query
        query = "SELECT timestamp, service_name, level, message FROM log_entries WHERE 1=1"
        params = []

        if service_name:
            query += " AND service_name = %s"
            params.append(service_name)

        if level:
            query += " AND level = %s"
            params.append(level.upper())

        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(tail)

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        if not logs:
            print("No logs found")
            return

        # Print logs in reverse (oldest first)
        print(f"\n📋 Showing {len(logs)} most recent logs:\n")
        for timestamp, svc, lvl, msg in reversed(logs):
            # Color code by level
            color = {
                'ERROR': '\033[91m',    # Red
                'WARNING': '\033[93m',  # Yellow
                'INFO': '\033[92m',     # Green
                'DEBUG': '\033[94m'     # Blue
            }.get(lvl, '')
            reset = '\033[0m'

            print(f"{timestamp} [{color}{lvl:7s}{reset}] [{svc:15s}] {msg}")

    except Exception as e:
        print(f"❌ Error querying database: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='View HiveMatrix service logs')
    parser.add_argument('service', nargs='?', help='Service name (optional)')
    parser.add_argument('--tail', '-n', type=int, default=50, help='Number of lines to show')
    parser.add_argument('--level', '-l', help='Filter by level (ERROR, WARNING, INFO, DEBUG)')

    args = parser.parse_args()
    view_logs(args.service, args.tail, args.level)
