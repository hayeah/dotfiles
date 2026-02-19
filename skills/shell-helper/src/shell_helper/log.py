"""Logging setup for shell-helper."""

from __future__ import annotations

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Configure stdlib logging with a simple format."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
    )
