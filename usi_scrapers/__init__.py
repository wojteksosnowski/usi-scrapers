"""
USI Scrapers Package
"""
import logging

__version__ = "0.7.9"

class USILoggerAdapter(logging.LoggerAdapter):
    """Adds version information to every log message."""
    def process(self, msg, kwargs):
        return f"[usi-scrapers v{self.extra['version']}] {msg}", kwargs

def get_logger(name: str) -> logging.LoggerAdapter:
    """Returns a logger adapter that prepends the package version."""
    logger = logging.getLogger(name)
    return USILoggerAdapter(logger, {"version": __version__})

# Public API for data mapping
from .mapping import get_mapping, resolve_path, load_mapping
from .utils.classifier import classify_segment

__all__ = ["get_logger", "get_mapping", "resolve_path", "load_mapping", "classify_segment"]
