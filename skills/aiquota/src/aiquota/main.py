"""aiquota — report remaining quota for Claude Code and Codex."""

from __future__ import annotations

from dataclasses import dataclass
import getpass
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLAUDE_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_OAUTH_SCOPES = [
    "user:profile",
    "user:inference",
    "user:sessions:claude_code",
    "user:mcp_servers",
    "user:file_upload",
]
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


@dataclass
class ClaudeCredsSource:
    kind: str
    location: str
    account: str | None = None
    service: str | None = None
    path: Path | None = None


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


def _claude_oauth_token_url() -> str:
    custom = os.environ.get("CLAUDE_CODE_CUSTOM_OAUTH_URL")
    if custom:
        return custom.rstrip("/") + "/v1/oauth/token"
    local = os.environ.get("CLAUDE_LOCAL_OAUTH_API_BASE")
    if local:
        return local.rstrip("/") + "/v1/oauth/token"
    return CLAUDE_OAUTH_TOKEN_URL


def _claude_oauth_client_id() -> str:
    return os.environ.get("CLAUDE_CODE_OAUTH_CLIENT_ID", CLAUDE_OAUTH_CLIENT_ID)


def _claude_oauth_scopes(oauth: dict[str, Any]) -> list[str]:
    scopes = oauth.get("scopes")
    if isinstance(scopes, str):
        parsed = [scope for scope in scopes.split(" ") if scope]
        if parsed:
            return parsed
    if isinstance(scopes, list):
        parsed = [str(scope) for scope in scopes if scope]
        if parsed:
            return parsed
    return CLAUDE_OAUTH_SCOPES


def _claude_oauth_expires_at_ms(expires_at: Any) -> float | None:
    if expires_at is None:
        return None
    if isinstance(expires_at, str):
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.timestamp() * 1000
    try:
        return float(expires_at)
    except (TypeError, ValueError):
        return None


def _claude_oauth_expires_soon(expires_at: Any, buffer_ms: int = 300_000) -> bool:
    expires_at_ms = _claude_oauth_expires_at_ms(expires_at)
    if expires_at_ms is None:
        return False
    return time.time() * 1000 + buffer_ms >= expires_at_ms


def _save_claude_creds(source: ClaudeCredsSource, creds: dict[str, Any]) -> str | None:
    payload = json.dumps(creds, separators=(",", ":"))
    if source.kind == "file" and source.path is not None:
        source.path.parent.mkdir(parents=True, exist_ok=True)
        source.path.write_text(payload)
        os.chmod(source.path, 0o600)
        return None
    if source.kind == "keychain" and source.account and source.service:
        payload_hex = payload.encode("utf-8").hex()
        script = (
            f'add-generic-password -U -a "{source.account}" '
            f'-s "{source.service}" -X "{payload_hex}"\n'
        )
        proc = subprocess.run(
            ["security", "-i"],
            input=script,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            return None
        stderr = proc.stderr.strip() or proc.stdout.strip()
        return f"failed to save refreshed Claude credentials to {source.location}: {stderr}"
    return f"unsupported Claude credential source: {source.location}"


def _refresh_claude_creds(
    creds: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    oauth = creds.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None, "missing claudeAiOauth in stored credentials"
    refresh_token = oauth.get("refreshToken")
    if not refresh_token:
        return None, "Claude OAuth refresh token missing"

    body = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": _claude_oauth_client_id(),
            "scope": " ".join(_claude_oauth_scopes(oauth)),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _claude_oauth_token_url(),
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "claude-cli",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace").strip()
        detail = f"HTTP Error {e.code}: {e.reason}"
        if body_text:
            detail += f" — {body_text[:200]}"
        return None, f"Claude OAuth refresh failed: {detail}"
    except Exception as e:
        return None, f"Claude OAuth refresh failed: {e}"

    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not access_token or expires_in is None:
        return None, "Claude OAuth refresh failed: missing access_token or expires_in"

    refreshed = dict(creds)
    refreshed_oauth = dict(oauth)
    refreshed_oauth["accessToken"] = access_token
    refreshed_oauth["refreshToken"] = payload.get("refresh_token", refresh_token)
    refreshed_oauth["expiresAt"] = int(time.time() * 1000 + float(expires_in) * 1000)
    if payload.get("scope"):
        refreshed_oauth["scopes"] = [
            scope for scope in str(payload["scope"]).split(" ") if scope
        ]
    refreshed["claudeAiOauth"] = refreshed_oauth
    return refreshed, None


def _load_claude_creds() -> tuple[dict[str, Any] | None, ClaudeCredsSource | None, str | None]:
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
                return creds, ClaudeCredsSource(
                    kind="keychain",
                    location=f"keychain:{service}",
                    account=account,
                    service=service,
                ), None
            errors.append(err or f"bad keychain payload for {service}")

    for path in _claude_credential_paths():
        if not path.exists():
            continue
        creds, err = _load_claude_creds_from_payload(path.read_text(), str(path))
        if creds is not None:
            return creds, ClaudeCredsSource(kind="file", location=str(path), path=path), None
        errors.append(err or f"bad credentials file: {path}")

    checked = [f"keychain:{service}" for service in _claude_keychain_services()] + [
        str(path) for path in _claude_credential_paths()
    ]
    if errors:
        return None, None, "; ".join(errors)
    return None, None, "no Claude credentials found; checked " + ", ".join(checked)


def _claude_usage_request(token: str) -> tuple[dict[str, Any] | None, int | None, str | None]:
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
            return json.loads(resp.read()), resp.status, None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace").strip()
        detail = f"request failed: HTTP Error {e.code}: {e.reason}"
        if body_text:
            detail += f" — {body_text[:200]}"
        return None, e.code, detail
    except Exception as e:
        return None, None, f"request failed: {e}"


def _fetch_claude_raw() -> dict[str, Any]:
    creds, source, error = _load_claude_creds()
    if creds is None:
        return {"error": error or "missing Claude credentials"}
    oauth = creds["claudeAiOauth"]

    if oauth.get("refreshToken") and _claude_oauth_expires_soon(oauth.get("expiresAt")):
        refreshed, refresh_error = _refresh_claude_creds(creds)
        if refreshed is None:
            return {"error": refresh_error or "Claude OAuth refresh failed"}
        creds = refreshed
        if source is not None:
            _save_claude_creds(source, creds)
        oauth = creds["claudeAiOauth"]

    raw, status, request_error = _claude_usage_request(oauth["accessToken"])
    if raw is not None:
        return raw
    if status != 401 or not oauth.get("refreshToken"):
        return {"error": request_error or "request failed"}

    refreshed, refresh_error = _refresh_claude_creds(creds)
    if refreshed is None:
        return {"error": refresh_error or request_error or "Claude OAuth refresh failed"}
    creds = refreshed
    if source is not None:
        _save_claude_creds(source, creds)
    raw, _, retry_error = _claude_usage_request(creds["claudeAiOauth"]["accessToken"])
    if raw is not None:
        return raw
    return {"error": retry_error or request_error or "request failed"}


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
