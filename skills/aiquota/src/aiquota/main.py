"""aiquota — report remaining quota for Claude Code and Codex."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

CLAUDE_CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CODEX_AUTH = Path.home() / ".codex" / "auth.json"
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

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


def _fetch_claude_raw() -> dict[str, Any]:
    if not CLAUDE_CREDENTIALS.exists():
        return {"error": f"missing {CLAUDE_CREDENTIALS}"}
    try:
        creds = json.loads(CLAUDE_CREDENTIALS.read_text())
        token = creds["claudeAiOauth"]["accessToken"]
    except (json.JSONDecodeError, KeyError) as e:
        return {"error": f"bad credentials file: {e}"}

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


def _fmt_window(w: dict[str, Any] | None) -> str:
    if not w:
        return "n/a"
    return f"{w.get('used_percent', '?')}% (reset {w.get('resets_at', '?')})"


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

    lines: list[str] = []
    for name, v in result.items():
        label = name.capitalize()
        if "error" in v:
            lines.append(f"{label}: error — {v['error']}")
            continue
        plan = v.get("plan") or "?"
        by_type = {w["type"]: w for w in (v.get("windows") or [])}
        parts = " | ".join(f"{t}={_fmt_window(by_type.get(t))}" for t in ("5h", "7d"))
        lines.append(f"{label} ({plan}): {parts}")
    typer.echo("\n".join(lines))


def run() -> None:
    app()


if __name__ == "__main__":
    run()
