"""Tmux session management with project awareness."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import typer

from . import fzf
from .cli import fallback_group
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


def _enter_path(path: Path | None) -> None:
    """Attach/create project-named session for a resolved path."""
    name = session_name(path)
    if not name:
        typer.echo("Not in a project directory", err=True)
        raise typer.Exit(1)
    if not _session_exists(name):
        root_dir = str(project_root(path))
        _run(["tmux", "new-session", "-d", "-s", name, "-c", root_dir])
    _renumber_sessions()
    _tmux_attach(f"={name}")


def _fzf_pick(projects: list[tuple[str, Path]], query: str | None = None) -> None:
    """Interactive project picker — fzf over projects, then enter."""
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
        _enter_path(Path(path_str))


def _do_enter(query: str | None) -> None:
    """Unified enter: path, fuzzy match, or interactive picker."""
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind == "path":
        _enter_path(r.path)
    elif r.kind == "match":
        _enter_path(r.path)
    elif r.kind == "picker":
        _fzf_pick(r.matches)
    elif r.kind == "ambiguous":
        _fzf_pick(r.matches, query)


# ---------------------------------------------------------------------------
# default callback — `shell-helper tm` with no subcommand runs enter
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _do_enter(None)


# ---------------------------------------------------------------------------
# enter — attach or create project-named session
# ---------------------------------------------------------------------------


@app.command()
def enter(
    query: str = typer.Argument(None, help="Path or project name to match (default: fzf picker)"),
) -> None:
    """Attach to a project session.

    With no argument, opens an interactive fzf picker.
    With a directory path, enters that project directly.
    With a search string, fuzzy-matches against ~/github.com repos.
    """
    _do_enter(query)


# ---------------------------------------------------------------------------
# which — show what a query resolves to
# ---------------------------------------------------------------------------


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
