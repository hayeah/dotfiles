"""Tmux session management with project awareness."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from itertools import zip_longest
from pathlib import Path

import typer

from .project import (
    PROJECT_FILES,
    _git_remote_url,
    _name_from_files,
    _name_from_git,
    root as project_root,
)

app = typer.Typer(help="Tmux session management.")


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


def _in_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def _session_exists(name: str) -> bool:
    try:
        _run(["tmux", "has-session", "-t", f"={name}"])
        return True
    except subprocess.CalledProcessError:
        return False


def _tmux_attach(target: str) -> None:
    """Exec into tmux attach/switch — replaces the current process."""
    if _in_tmux():
        os.execvp("tmux", ["tmux", "switch-client", "-t", target])
    else:
        os.execvp("tmux", ["tmux", "attach-session", "-t", target])


def _is_project(root_dir: Path) -> bool:
    if (root_dir / ".git").exists():
        return True
    return any((root_dir / f).is_file() for f in PROJECT_FILES)


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
    if not _is_project(root_dir):
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


def _do_enter(path: Path | None) -> None:
    """Core logic for enter — attach/create project-named session."""
    name = session_name(path)
    if not name:
        typer.echo("Not in a project directory", err=True)
        raise typer.Exit(1)
    if not _session_exists(name):
        root_dir = str(project_root(path))
        _run(["tmux", "new-session", "-d", "-s", name, "-c", root_dir])
    _renumber_sessions()
    _tmux_attach(f"={name}")


def _github_projects() -> list[tuple[str, Path]]:
    """Return (user/repo, path) pairs for all projects under ~/github.com."""
    base = Path.home() / "github.com"
    if not base.is_dir():
        return []
    projects: list[tuple[str, Path]] = []
    for user_dir in sorted(base.iterdir()):
        if not user_dir.is_dir():
            continue
        for repo_dir in sorted(user_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            if _is_project(repo_dir):
                projects.append((f"{user_dir.name}/{repo_dir.name}", repo_dir))
    return projects


def _do_find() -> None:
    """Interactive project finder — fzf over ~/github.com repos, then enter."""
    fzf_ver = _fzf_version()
    if not fzf_ver:
        typer.echo("fzf is required for find", err=True)
        raise typer.Exit(1)

    projects = _github_projects()
    if not projects:
        typer.echo("No projects found under ~/github.com", err=True)
        raise typer.Exit(1)

    border_opts = _build_border_opts(fzf_ver)
    # Replace labels for project context
    border_opts = border_opts.replace("' Panes '", "' Projects '")
    border_opts = border_opts.replace("' Preview '", "' Files '")

    base = str(Path.home() / "github.com")
    fzf_input = "\n".join(label for label, _ in projects)
    lookup = {label: path for label, path in projects}

    tmux_opts = "--tmux center,50%,50% " if _in_tmux() else ""
    fzf_cmd = (
        "fzf --exit-0 --reverse "
        f"{tmux_opts}"
        f"{border_opts} "
        f"--preview 'ls {shlex.quote(base)}/{{}}' "
        "--preview-window=right,40%,nowrap"
    )

    try:
        r = subprocess.run(
            fzf_cmd, shell=True, input=fzf_input, capture_output=True, text=True, check=True,
        )
        selected = r.stdout.strip()
    except subprocess.CalledProcessError:
        return

    if not selected or selected not in lookup:
        return

    _do_enter(lookup[selected])


# ---------------------------------------------------------------------------
# default callback — `shell-helper tm` with no subcommand runs find
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _do_find()


# ---------------------------------------------------------------------------
# enter — attach or create project-named session
# ---------------------------------------------------------------------------


@app.command()
def enter(
    path: Path = typer.Argument(None, help="Directory to start from (default: cwd)"),
) -> None:
    """Attach to the project-named session, creating it when needed."""
    _do_enter(path)


# ---------------------------------------------------------------------------
# find — fzf project picker
# ---------------------------------------------------------------------------


@app.command()
def find() -> None:
    """Interactive project finder — pick from ~/github.com repos via fzf."""
    _do_find()


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


def _fzf_version() -> str | None:
    try:
        return _run(["fzf", "--version"]).split()[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _version_gte(actual: str, minimum: str) -> bool:
    def parts(v: str) -> list[int]:
        return [int(x) for x in v.split(".")]

    a, b = parts(actual), parts(minimum)
    for x, y in zip_longest(a, b, fillvalue=0):
        if x != y:
            return x > y
    return True


def _build_border_opts(fzf_ver: str) -> str:
    opts = ""
    if _version_gte(fzf_ver, "0.58.0"):
        opts += (
            "--input-border --input-label ' Search ' --info=inline-right "
            "--list-border --list-label ' Panes ' "
            "--preview-border --preview-label ' Preview ' "
        )
    if _version_gte(fzf_ver, "0.61.0"):
        opts += "--ghost 'type to search...' "
    return opts or "--preview-label='pane preview'"


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
    fzf_ver = _fzf_version()
    if not fzf_ver:
        typer.echo("fzf is required for select", err=True)
        raise typer.Exit(1)

    border_opts = _build_border_opts(fzf_ver)
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
