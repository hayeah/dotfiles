"""shell-helper — project root detection, name inference, and editor launching."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .editor import open_editor, open_editor_project
from .log import setup_logging
from .project import github_url as project_github_url
from .project import name as project_name
from .project import root as project_root
from .tmux import app as tmux_app

app = typer.Typer(help="Shell utilities for project detection and editor launching.")


@app.command()
def project(
    path: Path = typer.Argument(None, help="File or directory to start from (default: cwd)"),
) -> None:
    """Print project root, name, and GitHub URL as JSON."""
    setup_logging()
    info: dict[str, str] = {"root": str(project_root(path)), "name": project_name(path)}
    gh_url = project_github_url(path)
    if gh_url:
        info["github_url"] = gh_url
    typer.echo(json.dumps(info, indent=2))


# -- editor subcommand group --------------------------------------------------

editor_app = typer.Typer(help="Open an editor at the project root.")
app.add_typer(editor_app, name="editor", invoke_without_command=True)


@editor_app.callback(invoke_without_command=True)
def editor_default(
    ctx: typer.Context,
    path: Path = typer.Argument(None, help="File or directory to open"),
    editor: str = typer.Option(
        None, "--editor", "-e", help="Override editor command (default: $CODE_EDITOR or code)"
    ),
) -> None:
    """Open editor at the project root. If PATH is a file, also opens that file."""
    if ctx.invoked_subcommand is not None:
        return
    setup_logging()
    open_editor(path, editor)


@editor_app.command("project")
def editor_project_cmd(
    query: str = typer.Argument(..., help="Zoxide query to match a project"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Use fzf picker for zoxide results"
    ),
    editor: str = typer.Option(
        None, "--editor", "-e", help="Override editor command (default: $CODE_EDITOR or code)"
    ),
) -> None:
    """Use zoxide to find a project and open editor there."""
    setup_logging()
    open_editor_project(query, editor, interactive)


# -- tm subcommand group -------------------------------------------------------

app.add_typer(tmux_app, name="tm")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
