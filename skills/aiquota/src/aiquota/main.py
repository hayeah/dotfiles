"""aiquota — report remaining quota for Claude Code and Codex."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CODEX_AUTH = Path.home() / ".codex" / "auth.json"
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
console = Console()

app = typer.Typer(
    help="Report remaining Claude Code and Codex quotas.",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)


def _iso(epoch_or_str: Any) -> str | None:
    if epoch_or_str is None:
        return None
    if isinstance(epoch_or_str, str):
        return epoch_or_str
    try:
        return datetime.fromtimestamp(float(epoch_or_str), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _window(type_: str, used_percent: Any, resets_at: Any) -> dict[str, Any] | None:
    if used_percent is None and resets_at is None:
        return None
    return {"type": type_, "used_percent": used_percent, "resets_at": _iso(resets_at)}


def _claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()


def _claude_keychain_services() -> list[str]:
    config_dir = str(_claude_config_dir().resolve()).encode("utf-8")
    hash_suffix = f"-{hashlib.sha256(config_dir).hexdigest()[:8]}" if os.environ.get(
        "CLAUDE_CONFIG_DIR"
    ) else ""
    oauth_suffixes = ("", "-custom-oauth", "-local-oauth", "-staging-oauth")
    services: list[str] = []
    for oauth_suffix in oauth_suffixes:
        base = f"Claude Code{oauth_suffix}-credentials"
        services.append(base)
        if hash_suffix:
            services.append(f"{base}{hash_suffix}")
    return services


def _claude_credential_paths() -> list[Path]:
    config_dir = _claude_config_dir()
    paths = [
        config_dir / ".credentials.json",
        Path.home() / ".claude" / ".credentials.json",
        Path.home() / ".claude.json",
    ]
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def _load_claude_creds_from_payload(
    payload: str, source: str
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        creds = json.loads(payload)
    except json.JSONDecodeError as e:
        return None, f"bad {source}: {e}"
    oauth = creds.get("claudeAiOauth") if isinstance(creds, dict) else None
    if not isinstance(oauth, dict):
        return None, f"missing claudeAiOauth in {source}"
    if not oauth.get("accessToken"):
        return None, f"missing claudeAiOauth.accessToken in {source}"
    return creds, None


def _load_claude_creds() -> tuple[dict[str, Any] | None, str | None]:
    errors: list[str] = []

    if sys.platform == "darwin":
        account = getpass.getuser()
        for service in _claude_keychain_services():
            try:
                proc = subprocess.run(
                    ["security", "find-generic-password", "-a", account, "-w", "-s", service],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
            except Exception as e:
                errors.append(f"keychain lookup failed for {service}: {e}")
                continue
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            creds, err = _load_claude_creds_from_payload(proc.stdout.strip(), f"keychain:{service}")
            if creds is not None:
                return creds, None
            errors.append(err or f"bad keychain payload for {service}")

    for path in _claude_credential_paths():
        if not path.exists():
            continue
        creds, err = _load_claude_creds_from_payload(path.read_text(), str(path))
        if creds is not None:
            return creds, None
        errors.append(err or f"bad credentials file: {path}")

    checked = [f"keychain:{service}" for service in _claude_keychain_services()] + [
        str(path) for path in _claude_credential_paths()
    ]
    if errors:
        return None, "; ".join(errors)
    return None, "no Claude credentials found; checked " + ", ".join(checked)


def _fetch_claude_raw() -> dict[str, Any]:
    creds, error = _load_claude_creds()
    if creds is None:
        return {"error": error or "missing Claude credentials"}
    token = creds["claudeAiOauth"]["accessToken"]

    req = urllib.request.Request(
        CLAUDE_USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": f"request failed: {e}"}


def _fetch_codex_raw() -> dict[str, Any]:
    """GET /wham/usage on chatgpt.com backend-api using ~/.codex/auth.json."""
    if not CODEX_AUTH.exists():
        return {"error": f"missing {CODEX_AUTH}"}
    try:
        auth = json.loads(CODEX_AUTH.read_text())
        token = auth["tokens"]["access_token"]
        account_id = auth["tokens"].get("account_id")
    except (json.JSONDecodeError, KeyError) as e:
        return {"error": f"bad codex auth.json: {e}"}

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "codex-cli",
        "Accept": "application/json",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
    req = urllib.request.Request(CODEX_USAGE_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": f"request failed: {e}"}


def claude_quota() -> dict[str, Any]:
    raw = _fetch_claude_raw()
    if "error" in raw:
        return {"provider": "claude", "error": raw["error"]}

    sources = [
        ("5h", raw.get("five_hour")),
        ("7d", raw.get("seven_day")),
        ("7d_sonnet", raw.get("seven_day_sonnet")),
        ("7d_opus", raw.get("seven_day_opus")),
    ]
    windows: list[dict[str, Any]] = []
    for type_, src in sources:
        if not src:
            continue
        w = _window(type_, src.get("utilization"), src.get("resets_at"))
        if w is not None:
            windows.append(w)

    return {
        "provider": "claude",
        "plan": None,
        "windows": windows,
        "extra_usage": raw.get("extra_usage"),
        "raw": raw,
    }


def codex_quota() -> dict[str, Any]:
    raw = _fetch_codex_raw()
    if "error" in raw:
        return {"provider": "codex", "error": raw["error"]}

    rate_limit = raw.get("rate_limit") or {}
    sources = [
        ("5h", rate_limit.get("primary_window")),
        ("7d", rate_limit.get("secondary_window")),
    ]
    windows: list[dict[str, Any]] = []
    for type_, src in sources:
        if not src:
            continue
        w = _window(type_, src.get("used_percent"), src.get("reset_at"))
        if w is not None:
            windows.append(w)

    return {
        "provider": "codex",
        "plan": raw.get("plan_type"),
        "windows": windows,
        "credits": raw.get("credits"),
        "raw": raw,
    }


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _pretty_table(result: dict[str, Any]) -> Table:
    table = Table(show_header=True)
    table.add_column("Provider", no_wrap=True, style="bold")
    table.add_column("Plan", no_wrap=True)
    table.add_column("Window", no_wrap=True)
    table.add_column("Used", justify="right", no_wrap=True)
    table.add_column("Reset / Error")

    for name, payload in result.items():
        label = name.capitalize()
        plan = str(payload.get("plan") or "-")
        if "error" in payload:
            table.add_row(label, plan, "error", "-", str(payload["error"]), style="red")
            continue

        windows = payload.get("windows") or []
        if not windows:
            table.add_row(label, plan, "-", "-", "-")
            continue

        first = True
        for window in windows:
            table.add_row(
                label if first else "",
                plan if first else "",
                str(window.get("type") or "-"),
                _fmt_percent(window.get("used_percent")),
                str(window.get("resets_at") or "-"),
            )
            first = False
    return table


@app.callback(invoke_without_command=True)
def show(
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Human-readable summary"),
    raw: bool = typer.Option(False, "--raw", help="Include raw provider payloads"),
    only: str = typer.Option(
        "both", "--only", help="Which provider to report: claude, codex, or both"
    ),
) -> None:
    """Print quota info (JSON by default)."""
    result: dict[str, Any] = {}
    if only in ("claude", "both"):
        result["claude"] = claude_quota()
    if only in ("codex", "both"):
        result["codex"] = codex_quota()

    if not raw:
        for v in result.values():
            v.pop("raw", None)

    if not pretty:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    console.print(_pretty_table(result))


def run() -> None:
    app()


if __name__ == "__main__":
    run()
