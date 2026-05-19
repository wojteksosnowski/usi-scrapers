"""
USI Scrapers Package
"""
import logging

__version__ = "0.5.6"

class USILoggerAdapter(logging.LoggerAdapter):
    """Adds version information to every log message."""
    def process(self, msg, kwargs):
        return f"[usi-scrapers v{self.extra['version']}] {msg}", kwargs

def get_logger(name: str) -> logging.LoggerAdapter:
    """Returns a logger adapter that prepends the package version."""
    logger = logging.getLogger(name)
    return USILoggerAdapter(logger, {"version": __version__})
