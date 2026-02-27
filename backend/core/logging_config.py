import logging
import logging.handlers
import sys
import os
import json
from contextvars import ContextVar
from typing import Optional

# ── 1. Context Tracking ──
# ContextVar allows us to track deployment_id across async/thread executions
# without having to pass it explicitly to every logger.info() call.
deployment_context: ContextVar[str] = ContextVar('deployment_id', default='system')

def set_deployment_context(deployment_id: str):
    """Set the deployment ID for the current execution context."""
    deployment_context.set(deployment_id)

def clear_deployment_context():
    """Reset the deployment context back to system."""
    deployment_context.set('system')

class DeploymentContextFilter(logging.Filter):
    """Injects the current deployment_id into every log record."""
    def filter(self, record):
        record.deployment_id = deployment_context.get()
        return True

# ── 2. Endpoint Filtering ──
class QuietLibrariesFilter(logging.Filter):
    """Silences noisy health checks and routine socket polling."""
    def filter(self, record):
        msg = record.getMessage()
        # Drop frequent, uninteresting HTTP requests
        if 'GET /socket.io/' in msg or 'POST /socket.io/' in msg:
            return False
        if 'GET /api/health' in msg:
            return False
        return True

# ── 3. JSON Formatter (Bonus for Production) ──
class JSONFormatter(logging.Formatter):
    """Outputs logs as single-line JSON strings for ELK/Datadog ingest."""
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "deployment_id": getattr(record, "deployment_id", "system"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# ── 4. Main Configuration ──
def configure_logging(
    log_file: str = 'deployment.log',
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    use_json: bool = False
) -> logging.Logger:
    """
    Production-grade, idempotent logging configuration.
    Safe for Gunicorn/Flask reloads; prevents duplicate log entries.
    """
    root_logger = logging.getLogger()
    
    # [Idempotent Setup] Clear existing handlers to prevent duplicate lines on reload
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Root logger must catch everything; handlers will filter appropriately
    root_logger.setLevel(logging.DEBUG)

    # Context filter to attach [deployment_id] to all logs
    context_filter = DeploymentContextFilter()

    # Determine format
    if use_json or os.environ.get('FLASK_ENV') == 'production':
        formatter = JSONFormatter(datefmt='%Y-%m-%dT%H:%M:%S%z')
    else:
        # Standard clean output: 2026-02-25 10:00:00 - INFO - deployment_orchestrator - [dep_123] - Message
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)-8s - %(name)s - [%(deployment_id)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Console Handler (Stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    console_handler.setLevel(console_level)
    root_logger.addHandler(console_handler)

    # Rotating File Handler (Logs directory)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB strict limit
            backupCount=5               # Keep last 5 files (Max 50MB total disk usage)
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        file_handler.setLevel(file_level)  # Keep DEBUG in file for deep forensics
        root_logger.addHandler(file_handler)

    # ── 5. Suppress Noisy External Libraries ──
    # Werkzeug logs every HTTP request at INFO. We silence routing chatter but keep WARNING/ERROR
    werkzeug = logging.getLogger('werkzeug')
    werkzeug.setLevel(logging.INFO)
    werkzeug.addFilter(QuietLibrariesFilter())

    # Paramiko generates massive stack traces upon expected EC2 timeout banner drops.
    logging.getLogger('paramiko.transport').setLevel(logging.WARNING)
    
    # SQLAlchemy can log massive queries if set to DEBUG
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Third party networking noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('socketio.server').setLevel(logging.WARNING)
    logging.getLogger('engineio.server').setLevel(logging.WARNING)

    return logging.getLogger(__name__)
