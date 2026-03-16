"""hayeah.config — load settings from a TOML config file.

Set HAYEAH_CONFIG to point to a TOML file. If unset, defaults apply.

Example config:

    [log]
    dir = "~/.local/log"
    level = "INFO"
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class LogConfig:
    dir: Path | None = None
    level: str = "INFO"


@dataclass
class Config:
    log: LogConfig = field(default_factory=LogConfig)


_config: Config | None = None


def load() -> Config:
    """Load config from HAYEAH_CONFIG path, or return defaults."""
    global _config
    if _config is not None:
        return _config

    config_path = os.getenv("HAYEAH_CONFIG")
    if config_path:
        p = Path(config_path).expanduser()
        if p.is_file():
            with open(p, "rb") as f:
                raw = tomllib.load(f)
            _config = _parse(raw)
        else:
            _config = Config()
    else:
        _config = Config()

    return _config


def _parse(raw: dict) -> Config:
    cfg = Config()
    if "log" in raw:
        log_raw = raw["log"]
        if "dir" in log_raw:
            cfg.log.dir = Path(log_raw["dir"]).expanduser()
        if "level" in log_raw:
            cfg.log.level = str(log_raw["level"]).upper()
    return cfg
