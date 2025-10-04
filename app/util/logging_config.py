"""
Centralized logging configuration for the application.
Creates a rotating file handler and console handler with DEBUG level.
Logs are written under the project root's logs directory by default.
Override location with environment variable PROCESS_EDITOR_LOG_DIR.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

# Resolve project root relative to this file (app/util/.. -> repo root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


def resolve_log_dir(custom_dir: Optional[str] = None) -> str:
    # Priority: explicit -> env -> <project_root>/logs
    path = (
        custom_dir
        or os.environ.get("PROCESS_EDITOR_LOG_DIR")
        or os.path.join(PROJECT_ROOT, "logs")
    )
    return os.path.abspath(path)


def setup_logging(log_dir: Optional[str] = None, filename: str = "process_editor.log", level: int = logging.DEBUG) -> str:
    """Configure root logging once. Returns the log file full path.

    Args:
        log_dir: Optional base directory for logs. If None, uses resolve_log_dir().
        filename: Log file name.
        level: Minimum logging level.
    """
    target_dir = resolve_log_dir(log_dir)
    os.makedirs(target_dir, exist_ok=True)
    log_path = os.path.join(target_dir, filename)

    root = logging.getLogger()
    # If we already configured our handlers, bail out fast
    if getattr(root, "_pe_logging_configured", False):
        return log_path

    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (rotating)
    try:
        file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:
        # If file handler fails (permissions, path), fallback to console only
        pass

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Mark configured and emit one line telling where logs go
    setattr(root, "_pe_logging_configured", True)
    logging.getLogger(__name__).info("Logging initialized. File: %s", log_path)
    return log_path
