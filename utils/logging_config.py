import logging
import logging.handlers
import os
import json
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'funcName': record.funcName,
            'line': record.lineno
        }

        # Include extra data if provided
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            payload.update(record.extra)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(app_name: str = 'vanet', log_dir: str = None, level: int = logging.INFO):
    """Configure structured JSON logging with rotation.

    - log_dir: directory to store logs (env VANET_LOG_DIR overrides), falls back to /var/log/vanet or ./logs
    - rotation: file rotates at 5 MB with 5 backups
    """
    env_dir = os.environ.get('VANET_LOG_DIR')
    if env_dir:
        log_dir = env_dir

    if not log_dir:
        # Prefer system dir if writable, otherwise use backend/updated_logs/<app_name>
        prefer = '/var/log/vanet'
        try:
            os.makedirs(prefer, exist_ok=True)
            testfile = os.path.join(prefer, '.perm_test')
            with open(testfile, 'w') as f:
                f.write('ok')
            os.remove(testfile)
            log_dir = prefer
        except Exception:
            # Fallback to backend/updated_logs/<app_name> inside repository root
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            backend_logs = os.path.join(repo_root, 'backend', 'updated_logs', app_name)
            log_dir = backend_logs

    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid adding duplicate handlers if called multiple times
    # Avoid adding duplicate handlers for the same app/file
    for h in logger.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler) and hasattr(h, 'baseFilename'):
            try:
                if os.path.basename(h.baseFilename) == f"{app_name}.log":
                    return logger
            except Exception:
                continue

    # Rotating file handler
    logfile = os.path.join(log_dir, f"{app_name}.log")
    fh = logging.handlers.RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(JsonFormatter())

    # Console handler with simple formatter
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)

    # Return root logger for convenience
    return logger
