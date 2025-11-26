"""Logging utilities with a consistent format across modules."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger configured with a simple timestamped format."""

    logger = logging.getLogger(name)
    if not logging.getLogger().handlers:
        logging.basicConfig(format=LOG_FORMAT, level=level)
    logger.setLevel(level)
    return logger

