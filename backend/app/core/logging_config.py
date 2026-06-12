# backend/app/core/logging_config.py
import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging(env: str = "development") -> None:
    """
    Configure root logger.
    - development: human-readable format with timestamp and level
    - production:  JSON format for log aggregation (ELK, Loki, CloudWatch, etc.)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if env == "production":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress noisy libraries that log at DEBUG/INFO unnecessarily
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
