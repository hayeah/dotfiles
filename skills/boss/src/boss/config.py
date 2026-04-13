"""Load boss.toml with ${VAR} env interpolation and $$ escape.

Resolution order:
  1. Explicit path (passed as argument)
  2. $BOSS_CONFIG env var
  3. ./boss.toml in cwd
  4. None (no config found → caller uses defaults)
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_ENV_RE = re.compile(r"\$\$|\$\{([^}]+)\}")


def _interpolate_env(text: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        if m.group(0) == "$$":
            return "$"
        return os.environ.get(m.group(1), "")

    return _ENV_RE.sub(_repl, text)


def _expand_path(s: str) -> str:
    if s.startswith("~/") or s == "~":
        return str(Path.home()) + s[1:]
    return s


@dataclass
class DashboardConfig:
    port: int = 7777
    host: str = "0.0.0.0"


@dataclass
class BossConfig:
    workspace: str = ""
    tmux_session: str = "__boss"
    repos_root: str = ""
    skills: list[str] = field(default_factory=list)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)

    @property
    def workspace_path(self) -> Path:
        if self.workspace:
            return Path(self.workspace)
        return Path.cwd()


def resolve_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit)
    env = os.environ.get("BOSS_CONFIG", "")
    if env:
        return Path(env)
    candidate = Path.cwd() / "boss.toml"
    if candidate.is_file():
        return candidate
    return None


def load(path: str | None = None) -> BossConfig:
    resolved = resolve_config_path(path)
    if resolved is None:
        cfg = BossConfig()
        cfg.repos_root = _expand_path("~/")
        return cfg

    raw = resolved.read_text()
    interpolated = _interpolate_env(raw)
    data = tomllib.loads(interpolated)

    dashboard_data = data.get("dashboard", {})
    dashboard = DashboardConfig(
        port=dashboard_data.get("port", 7777),
        host=dashboard_data.get("host", "0.0.0.0"),
    )

    workspace = _expand_path(data.get("workspace", ""))
    repos_root = _expand_path(data.get("repos_root", "~/"))

    skills = [_expand_path(s) for s in data.get("skills", [])]

    return BossConfig(
        workspace=workspace,
        tmux_session=data.get("tmux_session", "__boss"),
        repos_root=repos_root,
        skills=skills,
        dashboard=dashboard,
    )
