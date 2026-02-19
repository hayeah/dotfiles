"""git-quick-clone - clone GitHub repos with smart defaults."""

from __future__ import annotations

from pathlib import Path

import typer

from .clone import RepoCloner, _normalize_clone_url, access_token, get_remote_url
from .log import setup_logging
from .parser import parse_repo_url

app = typer.Typer(help="Clone a GitHub repo with optional shallow depth or sparse checkout.")


@app.command()
def clone(
    repo_url: str = typer.Argument(..., help="Repository (user/repo or URL)"),
    dest_dir: str | None = typer.Argument(None, help="Destination directory"),
    shallow: int | None = typer.Option(
        None, "--shallow", "-s", help="Shallow clone depth (e.g. --shallow 1)"
    ),
    full: bool = typer.Option(False, "--full", "-f", help="Full clone (no filters)"),
    token: str | None = typer.Option(None, "--token", help="GitHub access token"),
) -> None:
    """Clone a GitHub repository with smart defaults."""
    setup_logging()

    repo_info = parse_repo_url(repo_url)
    repo_info.access_token = access_token(token)

    dest = Path(dest_dir or repo_info.dest_dir)
    if (dest / ".git").is_dir():
        existing = get_remote_url(dest)
        expected = _normalize_clone_url(repo_info.url)
        if existing == expected:
            typer.echo(dest.resolve())
            return
        typer.echo(
            f"Target '{dest}' already contains a different repo "
            f"(origin: {existing})",
            err=True,
        )
        raise typer.Exit(1)

    cloner = RepoCloner(repo_info, dest, shallow, full)
    final_path = cloner.clone()
    typer.echo(final_path)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
