import logging
import os
import sys
from pathlib import Path


def _parse_level(s: str | None) -> int:
    if not s:
        return logging.INFO
    s = s.strip()
    if s.isdigit():
        return int(s)
    return getattr(logging, s.upper(), logging.INFO)


class NamePrefixAllowFilter(logging.Filter):
    """Allow only records whose logger name matches one of the prefixes."""

    def __init__(self, prefixes: list[str]):
        super().__init__()
        self.prefixes = [p for p in (prefixes or []) if p]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.prefixes:
            return True
        name = record.name
        for p in self.prefixes:
            if name == p or name.startswith(p + "."):
                return True
        return False


def setup_logging() -> None:
    level = _parse_level(os.getenv("LOG_LEVEL", "INFO"))

    raw_filter = (os.getenv("LOG_FILTER") or "").strip()
    prefixes = [x.strip() for x in raw_filter.split(",") if x.strip()] if raw_filter else []

    output = (os.getenv("LOG_OUTPUT") or "stderr").strip()

    root = logging.getLogger()
    root.setLevel(level)

    for h in list(root.handlers):
        root.removeHandler(h)

    if output.lower() in ("stdout", "out"):
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
    elif output.lower() in ("stderr", "err", ""):
        handler = logging.StreamHandler(sys.stderr)
    else:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")

    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    if prefixes:
        handler.addFilter(NamePrefixAllowFilter(prefixes))

    root.addHandler(handler)
