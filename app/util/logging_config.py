"""
Centralized logging configuration for the application.
Creates a rotating file handler and console handler with DEBUG level.
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = "logs", filename: str = "process_editor.log", level: int = logging.DEBUG) -> None:
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    # Avoid duplicate handlers if setup_logging is called multiple times
    root = logging.getLogger()
    if getattr(root, "_pe_logging_configured", False):
        return

    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # mark configured
    setattr(root, "_pe_logging_configured", True)
