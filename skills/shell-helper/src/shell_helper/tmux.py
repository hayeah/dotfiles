"""Tmux session management with project awareness."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import typer

from . import fzf
from .cli import fallback_group
from .editor import _is_path_like, _ssh_path_exists, ssh_github_projects
from .project import (
    _git_remote_url,
    _name_from_files,
    _name_from_git,
    is_project,
    resolve,
)
from .project import root as project_root

app = typer.Typer(help="Tmux session management.", cls=fallback_group("enter"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(cmd: str | list[str], check: bool = True) -> str:
    """Run a command and return stripped stdout."""
    if isinstance(cmd, list):
        r = subprocess.run(cmd, capture_output=True, text=True, check=check)
    else:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
    return r.stdout.strip()


def _session_exists(name: str) -> bool:
    try:
        _run(["tmux", "has-session", "-t", f"={name}"])
        return True
    except subprocess.CalledProcessError:
        return False


def _tmux_attach(target: str) -> None:
    """Exec into tmux attach/switch — replaces the current process."""
    if fzf.in_tmux():
        os.execvp("tmux", ["tmux", "switch-client", "-t", target])
    else:
        os.execvp("tmux", ["tmux", "attach-session", "-t", target])


CLAUDE_CODE_CMD = "bunx @anthropic-ai/claude-code --dangerously-skip-permissions"


def _sanitize_session_name(name: str) -> str:
    """Replace characters not allowed in tmux session names (. and :)."""
    return name.replace(".", "-").replace(":", "-")


def _session_name_from_remote(root_dir: Path) -> str | None:
    """Extract <user>/<repo> from git remote URL."""
    url = _git_remote_url(root_dir)
    if not url:
        return None
    # git@host:user/repo.git
    m = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    # https://host/user/repo.git
    m = re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    return None


def _session_name_from_path(root_dir: Path) -> str | None:
    """Extract <user>/<repo> from ~/github.com/<user>/<repo> path."""
    github_base = Path.home() / "github.com"
    try:
        rel = root_dir.resolve().relative_to(github_base)
        parts = rel.parts
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except ValueError:
        pass
    return None


def session_name(path: Path | None = None) -> str | None:
    """Derive tmux session name. Returns None if not in a project."""
    root_dir = project_root(path)
    if not is_project(root_dir):
        return None
    raw = (
        _session_name_from_path(root_dir)
        or _session_name_from_remote(root_dir)
        or _name_from_files(root_dir)
        or _name_from_git(root_dir)
        or root_dir.name
    )
    return _sanitize_session_name(raw)


def _renumber_sessions() -> None:
    """Rename digit-only sessions so they count upward from 1."""
    try:
        output = _run(["tmux", "list-sessions", "-F", "#S"])
    except subprocess.CalledProcessError:
        return
    sessions = [s for s in output.splitlines() if s.isdigit()]
    sessions.sort(key=int)
    for new_index, old_name in enumerate(sessions, start=1):
        if str(new_index) != old_name:
            _run(["tmux", "rename-session", "-t", old_name, str(new_index)])


def _ensure_session(path: Path | None) -> tuple[str, str]:
    """Ensure a tmux session exists for a project path. Returns (name, root_dir)."""
    name = session_name(path)
    if not name:
        typer.echo("Not in a project directory", err=True)
        raise typer.Exit(1)
    root_dir = str(project_root(path))
    if not _session_exists(name):
        _run(["tmux", "new-session", "-d", "-s", name, "-c", root_dir])
    return name, root_dir


def _enter_path(path: Path | None) -> None:
    """Attach/create project-named session for a resolved path."""
    name, _ = _ensure_session(path)
    _renumber_sessions()
    _tmux_attach(name)


def _cc_path(path: Path | None) -> None:
    """Create a new window running claude-code in the project session."""
    name, root_dir = _ensure_session(path)
    _run(f"tmux new-window -t {shlex.quote(name)} -c {shlex.quote(root_dir)} {shlex.quote(CLAUDE_CODE_CMD)}")
    _renumber_sessions()
    _tmux_attach(name)


def _fzf_pick_project(
    projects: list[tuple[str, Path]],
    query: str | None,
    action: callable,
) -> None:
    """Interactive project picker — fzf over projects, then run action on selected path."""
    base = str(Path.home() / "github.com")
    preview_cmd = f"ls {shlex.quote(base)}/{{}}"
    str_projects = [(label, str(path)) for label, path in projects]
    result = fzf.select_project(
        str_projects,
        query,
        list_label="Projects",
        preview_label="Files",
        preview_cmd=preview_cmd,
    )
    if result:
        _, path_str = result
        action(Path(path_str))


def _do_resolve(query: str | None, action: callable) -> None:
    """Resolve a project query and run action on the result."""
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind in ("path", "match"):
        action(r.path)
    elif r.kind == "picker":
        _fzf_pick_project(r.matches, None, action)
    elif r.kind == "ambiguous":
        _fzf_pick_project(r.matches, query, action)


# ---------------------------------------------------------------------------
# SSH remote attach via autossh
# ---------------------------------------------------------------------------


def _remote_session_name(remote_path: str) -> str:
    """Derive a tmux session name from a remote ~/github.com/<user>/<repo> path."""
    parts = [p for p in remote_path.split("/") if p]
    if "github.com" in parts:
        i = parts.index("github.com")
        if i + 2 < len(parts):
            return _sanitize_session_name(f"{parts[i + 1]}/{parts[i + 2]}")
    return _sanitize_session_name(parts[-1] if parts else "remote")


def _enter_ssh(host: str, remote_path: str) -> None:
    """Exec autossh into a tmux session on the remote host."""
    if shutil.which("autossh") is None:
        typer.echo("autossh not found. Install with: brew install autossh", err=True)
        raise typer.Exit(1)

    name = _remote_session_name(remote_path)
    remote_cmd = f"tmux new -A -s {shlex.quote(name)} -c {shlex.quote(remote_path)}"
    args = [
        "autossh",
        "-M", "0",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-t", host,
        remote_cmd,
    ]
    env = os.environ.copy()
    # Without this, autossh exits if the very first connection fails — we want it to keep trying.
    env.setdefault("AUTOSSH_GATETIME", "0")
    os.execvpe("autossh", args, env)


def _do_resolve_ssh(
    host: str,
    query: str | None,
    action: Callable[[str, str], None],
) -> None:
    """Resolve a remote project query via fzf/fuzzy, then run action(host, remote_path)."""
    if query and _is_path_like(query):
        remote_path = _ssh_path_exists(host, query)
        if remote_path:
            action(host, remote_path)
            return
        typer.echo(f"Path '{query}' not found on {host}", err=True)
        raise typer.Exit(1)

    projects = ssh_github_projects(host)
    if not projects:
        typer.echo(f"No projects found on {host}", err=True)
        raise typer.Exit(1)

    if query:
        q_lower = query.lower()
        matches = [(label, p) for label, p in projects if q_lower in label.lower()]
        if len(matches) == 1:
            action(host, matches[0][1])
            return
        if not matches:
            typer.echo(f"No projects matching '{query}' on {host}", err=True)
            raise typer.Exit(1)
        projects = matches

    result = fzf.select_project(
        projects, query, list_label=f"Projects ({host})", preview_label="Files",
    )
    if result:
        _, remote_path = result
        action(host, remote_path)


# ---------------------------------------------------------------------------
# default callback — `shell-helper tm` with no subcommand runs enter
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    ssh: Optional[str] = typer.Option(
        None, "--ssh", help="SSH host — attach tmux on the remote via autossh",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["ssh"] = ssh
    if ctx.invoked_subcommand is None:
        if ssh:
            _do_resolve_ssh(ssh, None, _enter_ssh)
        else:
            _do_resolve(None, _enter_path)


# ---------------------------------------------------------------------------
# enter — attach or create project-named session
# ---------------------------------------------------------------------------


@app.command()
def enter(
    ctx: typer.Context,
    query: str = typer.Argument(None, help="Path or project name to match (default: fzf picker)"),
) -> None:
    """Attach to a project session.

    With no argument, opens an interactive fzf picker.
    With a directory path, enters that project directly.
    With a search string, fuzzy-matches against ~/github.com repos.
    With --ssh, runs autossh + tmux on a remote host (auto-reconnects on drops).
    """
    ssh = ctx.obj.get("ssh") if ctx.obj else None
    if ssh:
        _do_resolve_ssh(ssh, query, _enter_ssh)
    else:
        _do_resolve(query, _enter_path)


# ---------------------------------------------------------------------------
# cc — launch claude-code in a project session
# ---------------------------------------------------------------------------


@app.command()
def cc(
    query: str = typer.Argument(None, help="Path or project name to match (default: fzf picker)"),
) -> None:
    """Launch claude-code in a project session.

    With no argument, opens an fzf picker over projects.
    With a query, fuzzy-matches against ~/github.com repos.
    """
    _do_resolve(query, _cc_path)


@app.command()
def which(
    query: str = typer.Argument(None, help="Path or project name to resolve"),
) -> None:
    """Show what a query would resolve to without entering."""
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind == "path":
        name = session_name(r.path)
        typer.echo(f"{r.path}  (session: {name})")
    elif r.kind == "match":
        name = session_name(r.path)
        typer.echo(f"{r.label}  {r.path}  (session: {name})")
    elif r.kind == "ambiguous":
        typer.echo(f"{len(r.matches)} matches:")
        for label, path in r.matches:
            typer.echo(f"  {label}  {path}")
    elif r.kind == "picker":
        typer.echo(f"{len(r.matches)} projects (would open fzf picker)")


# ---------------------------------------------------------------------------
# rename — renumber numeric sessions
# ---------------------------------------------------------------------------


@app.command()
def rename() -> None:
    """Rename digit-only sessions so they count upward from 1."""
    _renumber_sessions()


# ---------------------------------------------------------------------------
# select — fzf pane picker
# ---------------------------------------------------------------------------


@app.command()
def killall() -> None:
    """Kill all sessions except protected ones.

    Protected sessions are listed in $TMUX_KILL_PROTECT (comma-separated).
    """
    keep_raw = os.environ.get("TMUX_KILL_PROTECT", "")
    keep = {s.strip() for s in keep_raw.split(",") if s.strip()}

    try:
        output = _run(["tmux", "list-sessions", "-F", "#{session_name}"])
    except subprocess.CalledProcessError:
        typer.echo("No tmux server running", err=True)
        raise typer.Exit(1)

    all_sessions = output.splitlines()

    to_kill = []
    kept = []
    for s in all_sessions:
        if s in keep:
            kept.append(f"  {s} (TMUX_KILL_PROTECT)")
        else:
            to_kill.append(s)

    if kept:
        typer.echo("Keeping:")
        for line in kept:
            typer.echo(line)

    if not to_kill:
        typer.echo("Nothing to kill.")
        return

    for s in to_kill:
        typer.echo(f"Killing {s}")
        _run(["tmux", "kill-session", "-t", f"={s}"], check=False)

    _renumber_sessions()


@app.command()
def select(
    preview_pane: bool = typer.Option(True, "--preview/--no-preview", help="Live preview"),
    fzf_window_position: str = typer.Option("center,95%,95%", help="fzf --tmux position"),
    fzf_preview_window_position: str = typer.Option(
        "right,,,nowrap", help="fzf --preview-window position"
    ),
    list_panes_format: str = typer.Option(
        "pane_id session_name window_index pane_title pane_current_path pane_current_command",
        help="Space-separated tmux format tokens",
    ),
) -> None:
    """Interactive pane switcher using fzf."""
    fzf_ver = fzf.fzf_version()
    if not fzf_ver:
        typer.echo("fzf is required for select", err=True)
        raise typer.Exit(1)

    border_opts = fzf.build_border_opts(fzf_ver, list_label="Panes", preview_label="Preview")
    preview_opts = (
        f"--preview 'tmux capture-pane -ep -t {{1}}' "
        f"--preview-window={fzf_preview_window_position}"
        if preview_pane
        else ""
    )

    fmt_tokens = list_panes_format.split()
    tmux_fmt = " ".join(f"#{{{tok}}}" for tok in fmt_tokens)

    fzf_cmd = (
        "fzf --exit-0 --print-query --reverse "
        f"--tmux {shlex.quote(fzf_window_position)} "
        f"{border_opts} {preview_opts}"
    )
    pipeline = f"tmux list-panes -aF '{tmux_fmt}' | {fzf_cmd} | tail -1"

    try:
        selected_line = _run(pipeline)
    except subprocess.CalledProcessError:
        return

    if not selected_line:
        return

    pane_id = selected_line.split()[0]
    _tmux_attach(pane_id)
