"""hayeah.logger — structured logging for dotfiles tools."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

LOG_DIR = Path("~/.local/log").expanduser()

_shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    structlog.configure(
        processors=[
            *_shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _console_formatter() -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        foreign_pre_chain=_shared_processors,
    )


def _json_formatter() -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=_shared_processors,
    )


def new(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger with console + JSONL file output.

    Same name returns the same logger (idempotent).
    """
    _ensure_configured()

    stdlib_logger = logging.getLogger(name)

    # Already configured — return cached structlog wrapper
    if stdlib_logger.handlers:
        return structlog.get_logger(name)

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    stdlib_logger.setLevel(level)
    stdlib_logger.propagate = False  # don't leak to root

    # Console handler — pretty colored output to stderr
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_console_formatter())
    stdlib_logger.addHandler(console)

    # File handler — JSONL with rotation
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_h = RotatingFileHandler(
        LOG_DIR / f"{name}.jsonl",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_h.setFormatter(_json_formatter())
    stdlib_logger.addHandler(file_h)

    return structlog.get_logger(name)
