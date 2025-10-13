#!/usr/bin/env python3
"""
Log File Watcher - Monitors service log files and ingests them into PostgreSQL

This watches the logs/ directory for service stdout/stderr files and automatically
ingests new log lines into the centralized database.
"""

import os
import time
import re
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from models import db, LogEntry
from app import app

class LogFileHandler(FileSystemEventHandler):
    """Handles log file events and ingests new lines"""

    def __init__(self):
        self.file_positions = {}  # Track read positions for each file
        self.logs_dir = Path('logs')

    def on_modified(self, event):
        """Called when a log file is modified"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process .log files
        if not file_path.suffix == '.log':
            return

        # Extract service name from filename (e.g., "knowledgetree.stdout.log" -> "knowledgetree")
        match = re.match(r'([^.]+)\.(stdout|stderr)\.log', file_path.name)
        if not match:
            return

        service_name = match.group(1)
        log_type = match.group(2)

        self.ingest_new_lines(file_path, service_name, log_type)

    def ingest_new_lines(self, file_path, service_name, log_type):
        """Read and ingest new lines from a log file"""
        try:
            # Get current position for this file
            current_pos = self.file_positions.get(str(file_path), 0)

            with open(file_path, 'r') as f:
                # Seek to last read position
                f.seek(current_pos)

                # Read new lines
                new_lines = f.readlines()

                # Update position
                self.file_positions[str(file_path)] = f.tell()

            if not new_lines:
                return

            # Parse and insert log entries
            with app.app_context():
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Parse log level from line if present
                    level = 'INFO'
                    if 'ERROR' in line or 'error' in line.lower():
                        level = 'ERROR'
                    elif 'WARNING' in line or 'warning' in line.lower():
                        level = 'WARNING'
                    elif 'DEBUG' in line or 'debug' in line.lower():
                        level = 'DEBUG'
                    elif 'CRITICAL' in line or 'critical' in line.lower():
                        level = 'CRITICAL'

                    # Create log entry
                    log_entry = LogEntry(
                        service_name=service_name,
                        level=level,
                        message=line,
                        timestamp=datetime.utcnow(),
                        context={'source': log_type}
                    )

                    db.session.add(log_entry)

                db.session.commit()

        except Exception as e:
            print(f"Error ingesting logs from {file_path}: {e}")

def start_log_watcher():
    """Start the log file watcher"""
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)

    event_handler = LogFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(logs_dir), recursive=False)

    # Initialize file positions for existing files
    for log_file in logs_dir.glob('*.log'):
        # Start reading from end of existing files
        event_handler.file_positions[str(log_file)] = log_file.stat().st_size

    observer.start()
    print("Log watcher started, monitoring logs/ directory")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == '__main__':
    start_log_watcher()
