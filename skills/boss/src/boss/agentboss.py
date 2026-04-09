"""Subprocess wrapper around the agentboss CLI.

Resolves the agentboss binary once at import time and snapshots a private
copy. The boss spec calls this out as a safety property:

  > The agentboss binary MUST be pinned/cached rather than relying on a
  > gobin shim that an in-flight subagent in the agentboss repo can rewrite.

Resolution rules (strict — fail loudly):

  1. `agentboss` on PATH MUST be a gobin shim. The shim is a shell script
     containing a `# gobin: <abs-path>` header naming its source dir.
  2. That source dir MUST be `~/github.com/hayeah/agentboss/cli/agentboss`
     (the canonical checkout). Anything else is an error — usually it
     means a worktree-built shim is shadowing the real one.
  3. We then snapshot the cached binary at `~/.gobin/bins/agentboss` to a
     process-private tmp file and use that for the rest of the session.
     Mid-session `gobin install` runs in another subagent overwrite the
     cache, but our snapshot is immune.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


CANONICAL_SOURCE = Path.home() / "github.com" / "hayeah" / "agentboss" / "cli" / "agentboss"
GOBIN_BIN_CACHE = Path.home() / ".gobin" / "bins" / "agentboss"


class AgentbossError(Exception):
    pass


def _parse_gobin_source(shim_path: Path) -> Path | None:
    """Return the `# gobin: <path>` header from a gobin shim, or None."""
    try:
        with shim_path.open("r") as f:
            head = f.read(2048)
    except OSError:
        return None
    for line in head.splitlines():
        line = line.strip()
        if line.startswith("# gobin:"):
            return Path(line.split(":", 1)[1].strip())
    return None


def _resolve_binary() -> str:
    on_path = shutil.which("agentboss")
    if not on_path:
        raise AgentbossError(
            "agentboss not found on PATH.\n"
            "install it with:\n"
            f"  cd {CANONICAL_SOURCE.parents[1]} && gobin install ./cli/agentboss"
        )

    shim = Path(on_path)
    source = _parse_gobin_source(shim)
    if source is None:
        raise AgentbossError(
            f"agentboss at {shim} is not a gobin shim "
            f"(no `# gobin:` header found).\n"
            f"the boss CLI requires a gobin shim built from {CANONICAL_SOURCE}.\n"
            f"reinstall with:\n"
            f"  cd {CANONICAL_SOURCE.parents[1]} && gobin install ./cli/agentboss"
        )

    if source.resolve() != CANONICAL_SOURCE.resolve():
        raise AgentbossError(
            f"agentboss shim at {shim} points at {source}, not the canonical "
            f"source {CANONICAL_SOURCE}.\n"
            f"this usually means a worktree-built shim is shadowing the real "
            f"one — `gobin install` from a worktree repoints the global shim. "
            f"reinstall from the main checkout:\n"
            f"  cd {CANONICAL_SOURCE.parents[1]} && gobin install ./cli/agentboss"
        )

    if not GOBIN_BIN_CACHE.exists():
        # Force the shim to do its first build so the cache exists, then snapshot.
        proc = subprocess.run(
            [str(shim), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if not GOBIN_BIN_CACHE.exists():
            raise AgentbossError(
                f"failed to build agentboss cache at {GOBIN_BIN_CACHE}: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )

    # Snapshot the cached binary to a process-private tmp file. The boss
    # session may live for hours; an in-flight subagent rebuilding agentboss
    # would otherwise overwrite the cache out from under us.
    fd, snapshot = tempfile.mkstemp(prefix=f"boss-agentboss-{os.getpid()}-", suffix="")
    os.close(fd)
    shutil.copy2(GOBIN_BIN_CACHE, snapshot)
    os.chmod(snapshot, 0o755)
    return snapshot


_BINARY: str | None = None


def binary() -> str:
    global _BINARY
    if _BINARY is None:
        _BINARY = _resolve_binary()
    return _BINARY


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary(), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def ls_all() -> list[dict[str, Any]]:
    """Return all live agentboss sessions as a list of state dicts.

    `agentboss ls --json` prints the array on stdout. When there are no
    processes it prints `no processes` to stderr and emits nothing on
    stdout — we treat that as an empty list.
    """
    proc = _run(["ls", "--json"], check=False)
    if proc.returncode != 0:
        # Some agentboss versions exit non-zero on the empty case; tolerate.
        if "no processes" in (proc.stderr or "") + (proc.stdout or ""):
            return []
        raise AgentbossError(
            f"agentboss ls failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        raise AgentbossError(f"agentboss ls returned non-JSON: {e}\n{out!r}")
    if not isinstance(data, list):
        raise AgentbossError(f"agentboss ls expected array, got {type(data).__name__}")
    return data


def session_for_cwd(cwd: Path) -> dict[str, Any] | None:
    """Return the live agentboss session whose cwd is exactly `cwd`, or None.

    `agentboss ls --filter cwd:<path>` does *substring* matching, so we
    re-filter for exact equality here. We also drop sessions whose state is
    `child_exited` / empty (the agentboss store usually prunes them, but a
    just-died one may still be in the listing).
    """
    target = str(cwd.resolve())
    for entry in ls_all():
        entry_cwd = entry.get("cwd", "")
        if not entry_cwd:
            continue
        try:
            if str(Path(entry_cwd).resolve()) != target:
                continue
        except OSError:
            if entry_cwd != target:
                continue
        state = entry.get("state", "")
        if state in ("child_exited", "dead", ""):
            continue
        return entry
    return None


def run(cwd: Path, command: list[str], detector: str = "claude") -> dict[str, Any]:
    """Spawn a supervised CLI in `cwd`. Returns the JSON descriptor agentboss prints."""
    args = ["run", "--detector", detector, "--cwd", str(cwd), "--", *command]
    proc = _run(args, check=False)
    if proc.returncode != 0:
        raise AgentbossError(
            f"agentboss run failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.strip()
    # `agentboss run` may print log lines before the JSON descriptor — grab the
    # last `{...}` block.
    last_brace = out.rfind("{")
    if last_brace < 0:
        raise AgentbossError(f"agentboss run produced no JSON descriptor:\n{out}")
    try:
        return json.loads(out[last_brace:])
    except json.JSONDecodeError as e:
        raise AgentbossError(f"agentboss run JSON parse error: {e}\n{out!r}")


def send(key: str, message: str) -> None:
    """Send a one-line message to the agent and submit it.

    For short / single-line messages this is fine, but for multi-line content
    use `submit(...)` — `agentboss send` fires Enter only 100ms after the text,
    which a long paste hasn't finished settling by.
    """
    proc = _run(["send", key, message], check=False)
    if proc.returncode != 0:
        raise AgentbossError(
            f"agentboss send {key!r} failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )


def _capture_input_line(key: str) -> str:
    """Return the bottom of the agent's pane (the input area)."""
    proc = _run(["output", key, "-n", "8"], check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _input_has_pending(pane: str) -> bool:
    """True if the input area shows a paste placeholder or buffered text.

    Claude's input prompt looks like `❯ ` when empty; `❯ [Pasted text #1 ...]`
    when a paste is buffered; `❯ some literal text` when chars are buffered.
    """
    for line in pane.splitlines():
        stripped = line.strip()
        if not stripped.startswith("❯"):
            continue
        # Strip the prompt marker and surrounding whitespace.
        rest = stripped[1:].strip()
        if not rest:
            return False
        return True
    return False


def submit(key: str, message: str, attempts: int = 4) -> None:
    """Send a (possibly multi-line) message and ensure it's actually submitted.

    Strategy:
      1. Send the text with `--no-enter`.
      2. Poll the pane until the input area shows the buffered content
         (paste placeholder or literal text) — confirms claude has finished
         processing the paste.
      3. Send Enter via `--keys`.
      4. Re-check the pane: if the input is still non-empty, send Enter again
         (up to `attempts` times). This handles the race where the Enter
         arrives mid-paste-finalization and gets absorbed.

    Raises AgentbossError if the input is still buffered after all attempts.
    """
    import time

    text_proc = _run(["send", key, message, "--no-enter"], check=False)
    if text_proc.returncode != 0:
        raise AgentbossError(
            f"agentboss send {key!r} (text) failed: {text_proc.stderr.strip()}"
        )

    # Wait for the paste to land in the input area.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if _input_has_pending(_capture_input_line(key)):
            break
        time.sleep(0.1)

    for attempt in range(attempts):
        # Small settle delay before sending Enter, longer on later attempts.
        time.sleep(0.2 + 0.2 * attempt)
        enter_proc = _run(["send", key, "Enter", "--keys"], check=False)
        if enter_proc.returncode != 0:
            raise AgentbossError(
                f"agentboss send {key!r} (Enter) failed: {enter_proc.stderr.strip()}"
            )
        # Verify the input was cleared.
        time.sleep(0.3)
        if not _input_has_pending(_capture_input_line(key)):
            return

    raise AgentbossError(
        f"failed to submit message to {key!r}: input still buffered after {attempts} Enter presses"
    )
