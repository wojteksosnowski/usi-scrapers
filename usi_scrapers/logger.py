import logging

__version__ = "1.3.9"

class USILoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[usi-scrapers v{self.extra['version']}] {msg}", kwargs

def get_logger(name: str) -> logging.LoggerAdapter:
    logger = logging.getLogger(name)
    return USILoggerAdapter(logger, {"version": __version__})
