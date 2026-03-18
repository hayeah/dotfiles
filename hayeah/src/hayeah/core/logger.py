"""hayeah.logger — structured logging for dotfiles tools.

Usage:

    from hayeah.core.logger import LogConfig, new

    log = new("my-tool", LogConfig(dir=Path("~/.local/log"), level="DEBUG"))
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

_shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

_configured = False


@dataclass
class LogConfig:
    dir: Path | None = None
    level: str = "INFO"


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


def new(name: str, cfg: LogConfig | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structured logger with console + optional JSONL file output.

    Pass a LogConfig to control log level and file output.
    Same name returns the same logger (idempotent).
    """
    _ensure_configured()

    stdlib_logger = logging.getLogger(name)

    # Already configured — return cached structlog wrapper
    if stdlib_logger.handlers:
        return structlog.get_logger(name)

    if cfg is None:
        cfg = LogConfig()

    stdlib_logger.setLevel(cfg.level)
    stdlib_logger.propagate = False  # don't leak to root

    # Console handler — pretty colored output to stderr
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_console_formatter())
    stdlib_logger.addHandler(console)

    # File handler — JSONL with rotation (only if log dir configured)
    if cfg.dir:
        log_dir = cfg.dir.expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_h = RotatingFileHandler(
            log_dir / f"{name}.jsonl",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_h.setFormatter(_json_formatter())
        stdlib_logger.addHandler(file_h)

    return structlog.get_logger(name)
