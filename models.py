from extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class LogEntry(db.Model):
    """
    Immutable log entries from all HiveMatrix services.
    Once written, these logs cannot be modified or deleted.
    """
    __tablename__ = 'log_entries'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    service_name = db.Column(db.String(50), nullable=False, index=True)
    level = db.Column(db.String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = db.Column(db.Text, nullable=False)
    context = db.Column(JSONB, nullable=True)  # Additional context data (JSON)
    trace_id = db.Column(db.String(36), nullable=True, index=True)  # For request tracing
    user_id = db.Column(db.String(100), nullable=True, index=True)  # User who triggered the log

    # Metadata
    hostname = db.Column(db.String(255), nullable=True)
    process_id = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'service_name': self.service_name,
            'level': self.level,
            'message': self.message,
            'context': self.context,
            'trace_id': self.trace_id,
            'user_id': self.user_id,
            'hostname': self.hostname,
            'process_id': self.process_id
        }


class ServiceStatus(db.Model):
    """
    Tracks the status and health of each HiveMatrix service.
    Updated by Helm's monitoring system.
    """
    __tablename__ = 'service_status'

    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False)  # running, stopped, error, unknown
    pid = db.Column(db.Integer, nullable=True)
    port = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    last_checked = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    health_status = db.Column(db.String(20), nullable=True)  # healthy, unhealthy, degraded
    health_message = db.Column(db.Text, nullable=True)
    cpu_percent = db.Column(db.Float, nullable=True)
    memory_mb = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'service_name': self.service_name,
            'status': self.status,
            'pid': self.pid,
            'port': self.port,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'health_status': self.health_status,
            'health_message': self.health_message,
            'cpu_percent': self.cpu_percent,
            'memory_mb': self.memory_mb
        }


class ServiceMetric(db.Model):
    """
    Time-series metrics for service performance monitoring.
    """
    __tablename__ = 'service_metrics'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(50), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    tags = db.Column(JSONB, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'service_name': self.service_name,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'tags': self.tags
        }
