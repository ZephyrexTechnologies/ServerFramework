import logging
import os
import sys
import traceback

from colorama import Back, Fore, Style, init

# Initialize colorama
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and enhanced traceback"""

    COLORS = {
        "DEBUG": Fore.WHITE,
        "INFO": Fore.LIGHTBLUE_EX,
        "WARNING": Fore.LIGHTYELLOW_EX,
        "ERROR": Fore.LIGHTRED_EX,
        "CRITICAL": Fore.RED + Back.WHITE,
    }

    def format(self, record):
        # Save original format
        original_fmt = self._style._fmt

        # Add colors
        color = self.COLORS.get(record.levelname, "")
        # Add file name and line number to the format
        self._style._fmt = (
            f"{color}%(asctime)s - %(name)s - %(levelname)s "
            f"[%(filename)s:%(lineno)d] - %(message)s{Style.RESET_ALL}"
        )

        # Format the message
        formatted_message = super().format(record)

        # Add traceback if exists with proper indentation and color
        if record.exc_info:
            # Get the full traceback
            tb_lines = traceback.format_exception(*record.exc_info)
            # Add proper indentation and color to each line
            formatted_tb = "\n".join(
                f"{Fore.RED}{line.rstrip()}{Style.RESET_ALL}" for line in tb_lines
            )
            formatted_message = f"{formatted_message}\n{formatted_tb}"

        # Restore original format
        self._style._fmt = original_fmt

        return formatted_message


# Configure root logger
def setup_enhanced_logging():
    # Set up basic configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with enhanced formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
        )
    )
    root_logger.addHandler(console_handler)

    # Set up global exception handler
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception


# Example usage (you can remove this when implementing)
if __name__ == "__main__":
    setup_enhanced_logging()
    logger = logging.getLogger(__name__)

    try:
        # Test different log levels
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")

        # Test exception logging
        raise ValueError("Test exception with traceback")
    except Exception as e:
        logger.error("An error occurred", exc_info=True)
