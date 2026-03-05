"""gobin — go run shim manager CLI."""

from __future__ import annotations

from typing import Optional

import typer

from .gobin import GobinManager

app = typer.Typer(
    help="Manage go run shims for hackable Go tools.",
    no_args_is_help=True,
)


@app.command(
    "install",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def install_cmd(
    ctx: typer.Context,
    path_or_url: str = typer.Argument(
        ..., help="Local path or github.com/user/repo or github.com/user/repo/sub/pkg"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Override binary name (default: last path segment)"
    ),
    full: bool = typer.Option(
        False, "--full", help="Full clone instead of treeless partial clone"
    ),
) -> None:
    """Install a go run shim for a Go package.

    Extra args after -- are passed as build flags to go run:

        gobin install github.com/hayeah/foopkg/cli/foo -- -tags foo
    """
    build_flags = ctx.args  # everything after --
    mgr = GobinManager()
    shim = mgr.install(path_or_url, name=name, build_flags=build_flags or None, full=full)
    typer.echo(f"installed: {shim}")


@app.command("ls")
def ls_cmd() -> None:
    """List all gobin-managed shims."""
    mgr = GobinManager()
    shims = mgr.list_shims()
    if not shims:
        typer.echo("No gobin shims found.", err=True)
        return
    width = max(len(s.name) for s in shims)
    for s in shims:
        typer.echo(f"{s.name:<{width}}  {s.pkg}")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
