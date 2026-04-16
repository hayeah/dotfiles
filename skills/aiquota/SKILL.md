---
name: aiquota
description: Report remaining Claude Code and Codex quota (5h and 7d). Use when the user asks how much quota is left.
---

# aiquota

CLI that reports remaining quota for Claude Code (subscription) and Codex (ChatGPT plan).

- **Claude**: hits `https://api.anthropic.com/api/oauth/usage` with the local Claude OAuth token.
  - On macOS, reads the `Claude Code-credentials` keychain entry first.
  - Falls back to legacy credential files such as `~/.claude/.credentials.json`.
- **Codex**: reads `payload.rate_limits` from the newest entry of the latest rollout JSONL under `~/.codex/sessions/`.

## Setup

```bash
cd {baseDir} && uv tool install -e .
```

No secrets needed — Claude uses the local OAuth credentials, Codex reads local rollout files.

## Usage

```bash
aiquota                 # JSON, both providers
aiquota --pretty        # one-line summary per provider
aiquota --only codex
aiquota --only claude
```

Output (JSON) shape:

```json
{
  "claude": { ... /api/oauth/usage body ... },
  "codex": {
    "plan_type": "plus",
    "primary":   { "used_percent": 12.0, "window_minutes": 300,   "resets_at": 1776..., "resets_at_iso": "..." },
    "secondary": { "used_percent": 38.0, "window_minutes": 10080, "resets_at": 1776..., "resets_at_iso": "..." },
    "_source": "/Users/.../rollout-....jsonl"
  }
}
```

Errors surface per-provider as `{"error": "..."}` instead of exiting non-zero, so one broken side doesn't hide the other.

## When to Use

- "How much Claude/Codex quota do I have left?"
- Before a long session, to check the 5h and 7d caps.
- Scripted polling (feed the JSON into a statusline or alert).

## Notes

- Codex quota only updates after a Codex API response lands in a rollout — it can lag a minute or two.
- Claude quota only populates after the first API response in a session; out-of-session, `/api/oauth/usage` is the authoritative source.
