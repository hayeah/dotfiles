"""dotenv-ls — list env var names from .env files with override tracking."""

from __future__ import annotations

from pathlib import Path

import typer

from .parser import parse_env_files

app = typer.Typer()


@app.command()
def ls(
    env_paths: list[Path] = typer.Argument(
        ..., help=".env file paths (later files override earlier)"
    ),
) -> None:
    """List env var names from .env files. Later files override earlier ones."""
    entries = parse_env_files(env_paths)
    for entry in entries:
        if entry.comment:
            typer.echo(f"{entry.filepath}: {entry.name} {entry.comment}")
        else:
            typer.echo(f"{entry.filepath}: {entry.name}")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
