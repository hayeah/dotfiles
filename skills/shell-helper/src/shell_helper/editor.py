"""Editor launching with project picker and SSH remote support."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer

from . import fzf
from .cli import fallback_group
from .project import resolve

# ---------------------------------------------------------------------------
# Editor shim — dict-based abstraction for zed vs code/cursor
# ---------------------------------------------------------------------------


@dataclass
class EditorConfig:
    local: str
    ssh: str | None = None


EDITORS: dict[str, EditorConfig] = {
    "zed": EditorConfig(
        local="{editor} {path}",
        ssh="{editor} ssh://{host}{path}",
    ),
    "code": EditorConfig(
        local="{editor} {path}",
        ssh="{editor} --remote ssh-remote+{host} {path}",
    ),
    "cursor": EditorConfig(
        local="{editor} {path}",
        ssh="{editor} --remote ssh-remote+{host} {path}",
    ),
    "vim": EditorConfig(local="{editor} {path}"),
    "nvim": EditorConfig(local="{editor} {path}"),
}

DEFAULT_EDITOR = "zed"


def resolve_editor(name: str | None = None) -> tuple[str, EditorConfig]:
    """Return (editor_cmd, config) from name, $CODE_EDITOR, or default."""
    cmd = name or os.getenv("CODE_EDITOR", DEFAULT_EDITOR)
    config = EDITORS.get(cmd, EDITORS["code"])  # unknown editors use code-style patterns
    return cmd, config


def open_local(editor: str, config: EditorConfig, path: str) -> None:
    """Open editor locally at path."""
    cmd = config.local.format(editor=editor, path=shlex.quote(path))
    subprocess.run(cmd, shell=True, check=True)


def open_ssh(editor: str, config: EditorConfig, host: str, path: str) -> None:
    """Open editor with SSH remote at host:path."""
    pattern = config.ssh
    if pattern is None:
        typer.echo(f"{editor} does not support SSH remote opening", err=True)
        raise typer.Exit(1)
    cmd = pattern.format(editor=editor, host=host, path=path)
    subprocess.run(cmd, shell=True, check=True)


# ---------------------------------------------------------------------------
# Remote project discovery
# ---------------------------------------------------------------------------


def ssh_github_projects(host: str) -> list[tuple[str, str]]:
    """List ~/github.com/*/* projects on a remote host via SSH.

    Returns (user/repo, absolute_remote_path) pairs.
    """
    ssh_cmd = [
        "ssh", host,
        "for d in ~/github.com/*/*; do "
        "[ -d \"$d/.git\" ] && echo \"$d\"; "
        "done",
    ]
    try:
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return []

    projects: list[tuple[str, str]] = []
    for line in r.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("/")
        if len(parts) >= 2:
            label = f"{parts[-2]}/{parts[-1]}"
            projects.append((label, line))
    return projects


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fzf_select(
    projects: list[tuple[str, str]],
    query: str | None,
    *,
    preview_cmd: str | None = None,
    list_label: str = "Projects",
) -> tuple[str, str] | None:
    """Run fzf picker over projects, return (label, path) or None."""
    return fzf.select_project(
        projects,
        query,
        list_label=list_label,
        preview_label="Files",
        preview_cmd=preview_cmd,
    )


def _default_preview() -> str:
    base = str(Path.home() / "github.com")
    return f"ls {shlex.quote(base)}/{{}}"


def _open_resolved_local(query: str | None, editor_name: str | None = None) -> None:
    """Resolve query to a local project via fzf/fuzzy match, then open editor."""
    editor, config = resolve_editor(editor_name)
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind in ("path", "match"):
        open_local(editor, config, str(r.path))
    elif r.kind in ("picker", "ambiguous"):
        str_projects = [(label, str(path)) for label, path in r.matches]
        fzf_query = query if r.kind == "ambiguous" else None
        result = _fzf_select(str_projects, fzf_query, preview_cmd=_default_preview())
        if result:
            _, path = result
            open_local(editor, config, path)


def _open_resolved_ssh(
    host: str, query: str | None, editor_name: str | None = None,
) -> None:
    """Resolve query to a remote project via SSH + fzf, then open editor."""
    editor, config = resolve_editor(editor_name)
    projects = ssh_github_projects(host)

    if not projects:
        typer.echo(f"No projects found on {host}", err=True)
        raise typer.Exit(1)

    if query:
        q_lower = query.lower()
        matches = [
            (label, p) for label, p in projects if q_lower in label.lower()
        ]
        if len(matches) == 1:
            open_ssh(editor, config, host, matches[0][1])
            return
        elif not matches:
            typer.echo(f"No projects matching '{query}' on {host}", err=True)
            raise typer.Exit(1)
        projects = matches

    result = _fzf_select(projects, query)
    if result:
        _, path = result
        open_ssh(editor, config, host, path)


def _print_which(query: str | None) -> None:
    """Print what a query resolves to without acting."""
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind == "path":
        typer.echo(str(r.path))
    elif r.kind == "match":
        typer.echo(f"{r.label}  {r.path}")
    elif r.kind == "ambiguous":
        typer.echo(f"{len(r.matches)} matches:")
        for label, path in r.matches:
            typer.echo(f"  {label}  {path}")
    elif r.kind == "picker":
        typer.echo(f"{len(r.matches)} projects (would open fzf picker)")


# ---------------------------------------------------------------------------
# CLI app
# ---------------------------------------------------------------------------

app = typer.Typer(help="Open editor at a project.", cls=fallback_group("open"))


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    ssh: Optional[str] = typer.Option(None, "--ssh", help="SSH host for remote project"),
    editor_name: Optional[str] = typer.Option(
        None, "--editor", "-e", help="Override editor (default: $CODE_EDITOR or zed)",
    ),
) -> None:
    """Open editor at a project.

    With no argument, opens an interactive fzf picker over ~/github.com projects.
    With '.' or a directory path, opens editor at that path.
    With a search string, fuzzy-matches against ~/github.com repos.
    With --ssh, discovers projects on a remote host.
    """
    ctx.ensure_object(dict)
    ctx.obj["ssh"] = ssh
    ctx.obj["editor_name"] = editor_name
    if ctx.invoked_subcommand is None:
        if ssh:
            _open_resolved_ssh(ssh, None, editor_name)
        else:
            _open_resolved_local(None, editor_name)


@app.command("open")
def open_cmd(
    ctx: typer.Context,
    query: Optional[str] = typer.Argument(None, help="Path, project name, or '.' for cwd"),
) -> None:
    """Open editor at a resolved project."""
    ssh = ctx.obj.get("ssh")
    editor_name = ctx.obj.get("editor_name")
    if ssh:
        _open_resolved_ssh(ssh, query, editor_name)
    else:
        _open_resolved_local(query, editor_name)


@app.command()
def which(
    query: Optional[str] = typer.Argument(None, help="Path or project name to resolve"),
) -> None:
    """Show what a query would resolve to without opening."""
    _print_which(query)
