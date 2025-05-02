import logging
import os
import sys

from loguru import logger

# Remove default handler
logger.remove()

# Get log level from environment
log_level = os.getenv("LOG_LEVEL", "INFO")

# Define numeric log levels mapping
LOG_LEVEL_MAP = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}


# Detect if running under pytest
def is_running_under_pytest():
    return any(arg.endswith("pytest") for arg in sys.argv) or "pytest" in sys.modules


# Determine if we should use color in output
# - Use LOG_COLOR env var if set
# - Otherwise, auto-disable color when running under pytest
# - Default to color for normal terminal usage
if "LOG_COLOR" in os.environ:
    use_color = os.getenv("LOG_COLOR").lower() == "true"
else:
    use_color = not is_running_under_pytest()

# Create console handler with optional coloring
if use_color:
    format_string = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
else:
    format_string = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"

# Add console handler
logger.add(
    sys.stdout,
    colorize=use_color,
    format=format_string,
    level=log_level,
)

# Add file handler with rotation (never use color in files)
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logger.add(
    f"{log_dir}/app.log",
    rotation="10 MB",
    retention="1 week",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=log_level,
)


# Configure global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error(
        "Uncaught exception"
    )


sys.excepthook = handle_exception


class LoggerAdapter:
    """Adapter to make loguru compatible with standard logging"""

    def __init__(self, name):
        self.name = name
        self.handlers = []
        self._level = log_level
        # Store numeric level value for compatibility with uvicorn and other libraries
        self._level_no = LOG_LEVEL_MAP.get(
            log_level.upper() if isinstance(log_level, str) else log_level, 20
        )  # Default to INFO (20) if not found

    @property
    def level(self):
        # Always return the numeric level value, not the string
        return self._level_no

    def _format_message(self, msg, args, kwargs):
        """Format message with args and kwargs"""
        if args and "%" in msg:
            return msg % args
        return msg

    def debug(self, msg, *args, **kwargs):
        formatted_msg = self._format_message(msg, args, kwargs)
        logger.bind(name=self.name).debug(formatted_msg)

    def info(self, msg, *args, **kwargs):
        formatted_msg = self._format_message(msg, args, kwargs)
        logger.bind(name=self.name).info(formatted_msg)

    def warning(self, msg, *args, **kwargs):
        formatted_msg = self._format_message(msg, args, kwargs)
        logger.bind(name=self.name).warning(formatted_msg)

    def error(self, msg, *args, **kwargs):
        formatted_msg = self._format_message(msg, args, kwargs)
        exc_info = kwargs.pop("exc_info", None)
        if exc_info:
            logger.bind(name=self.name).opt(exception=exc_info).error(formatted_msg)
        else:
            logger.bind(name=self.name).error(formatted_msg)

    def critical(self, msg, *args, **kwargs):
        formatted_msg = self._format_message(msg, args, kwargs)
        exc_info = kwargs.pop("exc_info", None)
        if exc_info:
            logger.bind(name=self.name).opt(exception=exc_info).critical(formatted_msg)
        else:
            logger.bind(name=self.name).critical(formatted_msg)

    def exception(self, msg, *args, **kwargs):
        """Log message with severity 'ERROR' and exception info."""
        # Set exc_info to True to automatically include exception details
        kwargs["exc_info"] = True
        self.error(msg, *args, **kwargs)

    # Add all compatibility methods needed for pytest
    def addHandler(self, handler):
        self.handlers.append(handler)

    def removeHandler(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)

    def setLevel(self, level):
        if isinstance(level, str):
            self._level = level
            self._level_no = LOG_LEVEL_MAP.get(level.upper(), 20)
        else:
            # If it's already a numeric level
            self._level_no = level
            # Find the string representation
            for k, v in LOG_LEVEL_MAP.items():
                if v == level:
                    self._level = k
                    break

    def hasHandlers(self):
        return len(self.handlers) > 0

    def isEnabledFor(self, level):
        if isinstance(level, str):
            level_no = LOG_LEVEL_MAP.get(level.upper(), 0)
            return self._level_no <= level_no
        return self._level_no <= level

    # Add additional compatibility attributes and methods
    @property
    def propagate(self):
        return False

    @propagate.setter
    def propagate(self, value):
        pass


# Create a root logger for compatibility
root_logger = LoggerAdapter("root")


def setup_enhanced_logging():
    """
    Legacy function for setting up enhanced logging.
    This is now handled automatically when the module is imported.
    """
    pass


class LoguruHandler(logging.Handler):
    def emit(self, record):
        # Extract logging level from record
        level = record.levelname.lower()
        message = self.format(record)

        # Forward to appropriate loguru level
        logger_method = getattr(logger, level, logger.info)
        logger_method(message)


# Store original methods
original_logging_config = {
    "getLogger": logging.getLogger,
    "basicConfig": logging.basicConfig,
}


# Wrap getLogger to return our adapter
def get_logger(name=None):
    """Compatible replacement for logging.getLogger"""
    if name is None:
        return root_logger
    return LoggerAdapter(name)


# No-op for basicConfig as we configure via our own mechanism
def basic_config(**kwargs):
    """Compatible replacement for logging.basicConfig"""
    pass


# Apply patches
logging.getLogger = get_logger
logging.basicConfig = basic_config

# Store originals for restoration if needed
logging._original_logging = original_logging_config
