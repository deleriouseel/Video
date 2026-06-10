import logging
from pathlib import Path
from datetime import datetime

def setup_logging(log_path: Path) -> logging.Logger:
    """" Set up logging.
    Args:
        log_path: Path to the log file.
    Returns:
        Logger isntance for the application
    """

    logger = logging.getLogger("video_processor")
    logger.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    try:
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to set up file logging: {e}")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# Function to get logger in other files
def get_logger() -> logging.Logger:
    return logging.getLogger("video_processor")