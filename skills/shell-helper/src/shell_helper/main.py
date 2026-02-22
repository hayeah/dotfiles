"""shell-helper — project root detection, name inference, and editor launching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .cli import fallback_group
from .editor import _default_preview, _fzf_select, _print_which
from .editor import app as editor_app
from .log import setup_logging
from .project import github_url as project_github_url
from .project import name as project_name
from .project import resolve
from .project import root as project_root
from .tmux import app as tmux_app

app = typer.Typer(help="Shell utilities for project detection and editor launching.")


# -- project subcommand group -------------------------------------------------

project_app = typer.Typer(
    help="Project discovery and info.", cls=fallback_group("info"),
)
app.add_typer(project_app, name="project")


@project_app.callback(invoke_without_command=True)
def _project_default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _project_info(None)


@project_app.command("info")
def _project_info_cmd(
    path: Optional[Path] = typer.Argument(None, help="File or directory (default: cwd)"),
) -> None:
    """Print project root, name, and GitHub URL as JSON."""
    _project_info(path)


def _project_info(path: Path | None) -> None:
    setup_logging()
    info: dict[str, str] = {"root": str(project_root(path)), "name": project_name(path)}
    gh_url = project_github_url(path)
    if gh_url:
        info["github_url"] = gh_url
    typer.echo(json.dumps(info, indent=2))


@project_app.command("find")
def _project_find_cmd(
    query: Optional[str] = typer.Argument(
        None, help="Project name to match (default: fzf picker)",
    ),
) -> None:
    """Find a project and print its path.

    With no argument, opens an interactive fzf picker.
    With a search string, fuzzy-matches against ~/github.com repos.
    """
    setup_logging()
    r = resolve(query)

    if r.kind == "error":
        typer.echo(r.error, err=True)
        raise typer.Exit(1)
    elif r.kind in ("path", "match"):
        typer.echo(str(r.path))
    elif r.kind in ("picker", "ambiguous"):
        str_projects = [(label, str(path)) for label, path in r.matches]
        fzf_query = query if r.kind == "ambiguous" else None
        result = _fzf_select(str_projects, fzf_query, preview_cmd=_default_preview())
        if result:
            _, path_str = result
            typer.echo(path_str)


@project_app.command("which")
def _project_which_cmd(
    query: Optional[str] = typer.Argument(None, help="Path or project name to resolve"),
) -> None:
    """Show what a query would resolve to without acting."""
    setup_logging()
    _print_which(query)


# -- editor subcommand group --------------------------------------------------

app.add_typer(editor_app, name="editor")


# -- tm subcommand group -------------------------------------------------------

app.add_typer(tmux_app, name="tm")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
