"""
HiveMatrix Helm Logging Client

This module should be copied to other HiveMatrix services to enable
centralized logging to the Helm service.

Usage:
    from helm_logger import HelmLogger

    logger = HelmLogger('codex', 'http://localhost:5004')
    logger.info('Service started', context={'version': '1.0'})
    logger.error('Database connection failed', trace_id='abc-123')
"""

import requests
import logging
import json
from datetime import datetime
from typing import Dict, Optional, Any
import socket
import os

class HelmLogger:
    """Client for sending logs to HiveMatrix Helm"""

    def __init__(self, service_name: str, helm_url: str = 'http://localhost:5004'):
        """
        Initialize the Helm logger

        Args:
            service_name: Name of the service sending logs
            helm_url: URL of the Helm service
        """
        self.service_name = service_name
        self.helm_url = helm_url.rstrip('/')
        self.hostname = socket.gethostname()
        self.process_id = os.getpid()
        self.buffer = []
        self.buffer_size = 10  # Send logs in batches of 10

        # Also set up local logging as fallback
        self.local_logger = logging.getLogger(service_name)

    def _send_logs(self, logs: list):
        """Send logs to Helm service"""
        try:
            response = requests.post(
                f"{self.helm_url}/api/logs/ingest",
                json={
                    'service_name': self.service_name,
                    'logs': logs
                },
                timeout=5
            )
            if response.status_code != 200:
                self.local_logger.warning(f"Failed to send logs to Helm: {response.text}")
        except Exception as e:
            self.local_logger.warning(f"Failed to send logs to Helm: {e}")

    def _log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None,
             trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Internal logging method"""

        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message,
            'context': context,
            'trace_id': trace_id,
            'user_id': user_id,
            'hostname': self.hostname,
            'process_id': self.process_id
        }

        # Add to buffer
        self.buffer.append(log_entry)

        # Also log locally
        self.local_logger.log(
            getattr(logging, level),
            f"[{trace_id}] {message}" if trace_id else message
        )

        # Send if buffer is full
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def flush(self):
        """Send all buffered logs immediately"""
        if self.buffer:
            self._send_logs(self.buffer)
            self.buffer = []

    def debug(self, message: str, **kwargs):
        """Log a DEBUG message"""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log an INFO message"""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log a WARNING message"""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log an ERROR message"""
        self._log('ERROR', message, **kwargs)
        self.flush()  # Immediately send errors

    def critical(self, message: str, **kwargs):
        """Log a CRITICAL message"""
        self._log('CRITICAL', message, **kwargs)
        self.flush()  # Immediately send critical errors

    def __del__(self):
        """Ensure logs are flushed when object is destroyed"""
        self.flush()


# Flask integration helper
class HelmLogHandler(logging.Handler):
    """
    A logging handler that sends logs to Helm

    Usage with Flask:
        from helm_logger import HelmLogHandler

        helm_handler = HelmLogHandler('codex', 'http://localhost:5004')
        app.logger.addHandler(helm_handler)
    """

    def __init__(self, service_name: str, helm_url: str = 'http://localhost:5004'):
        super().__init__()
        self.helm_logger = HelmLogger(service_name, helm_url)

    def emit(self, record: logging.LogRecord):
        """Emit a log record"""
        try:
            # Extract context from record
            context = {
                'filename': record.filename,
                'function': record.funcName,
                'line': record.lineno,
                'module': record.module
            }

            # Check if there's additional context
            if hasattr(record, 'context'):
                context.update(record.context)

            # Send to Helm
            self.helm_logger._log(
                level=record.levelname,
                message=record.getMessage(),
                context=context,
                trace_id=getattr(record, 'trace_id', None),
                user_id=getattr(record, 'user_id', None)
            )

        except Exception:
            self.handleError(record)

    def close(self):
        """Flush logs before closing"""
        self.helm_logger.flush()
        super().close()
