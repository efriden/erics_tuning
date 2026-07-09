import logging
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from datetime import datetime

from tune.shared.util.paths import LOG_PATH


def setup_logging(
    log_dir: Path | None = None,
    file_level: int = logging.DEBUG,
    root_level: int = logging.WARNING,
    app_level: int = logging.DEBUG,
    enable_console=False,
) -> Logger:
    """
    Set up logging for piano tuner.

    Args:
        log_dir: Directory for log files (defaults to [project_root]/logs)
        file_level: Minimal level to write to file
        root_level: Root logging level (will apply to third-party libraries)
        app_level: App logging level (will apply to erics-tuning and all sublibraries)
        enable_console: Whether to log to console (usually False for TUI apps)
    """

    if not log_dir:
        log_dir = LOG_PATH

    log_dir.mkdir(exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()

    # Clear existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(root_level)

    # Main application log with rotation
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )

    file_handler.setLevel(file_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    logging.getLogger("erics_tuning").setLevel(app_level)

    return root_logger


def log_run_start() -> None:
    logger = logging.getLogger(__name__)
    separator = "=" * 80
    logger.info(f"{separator}")
    logger.info("NEW RUN STARTED")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Python: {sys.version.split()[0]}")
    logger.info(f"Command: {' '.join(sys.argv)}")
    logger.info(separator)


def complete_log(o, logger, hide_hidden: bool = True) -> None:
    """
    Convenience method for logging as much available info about an object as possible to debug.

    Args:
        o: Object to debug
        logger: Logger that will handle the request
        hide_hidden: if true hidden properties will also be logged
    """
    logger.debug(f"Object: {o}")
    logger.debug(f"dir(Object): {dir(o)}")
    for p in dir(o):
        if hide_hidden and p[0] == "_":
            continue
        try:
            value = getattr(o, p)
            logger.debug(f"{p}: {value}")
        except Exception as e:
            logger.debug(f"{p}: <error accessing: {e}>")
