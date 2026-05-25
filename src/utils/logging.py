"""Logging configuration — writes only to stderr so stdio transport stays clean."""
from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    """Configure root logging to stderr at the level set by LOG_LEVEL (default WARNING)."""
    raw_level = os.environ.get("LOG_LEVEL", "WARNING").strip().upper()
    level = getattr(logging, raw_level, logging.WARNING)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
