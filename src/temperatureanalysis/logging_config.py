"""
Logging Configuration
Sets up the global logger for the application.
"""
import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Configures the root logger for the 'temperatureanalysis' namespace.

    Args:
        level: Logging level (e.g. logging.DEBUG, logging.INFO)
        log_file: Optional path to save logs to a file.
    """
    # Get the logger for our package
    logger = logging.getLogger("temperatureanalysis")
    logger.setLevel(level)

    # Check if handlers already exist to avoid duplicate logs during reload/restart
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: Time - Module - Level - Message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # 2. File Handler (Optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info("Logging initialized.")
