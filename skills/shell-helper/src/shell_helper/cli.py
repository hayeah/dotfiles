"""Shared CLI utilities."""

from __future__ import annotations

import click
from typer.core import TyperGroup


def fallback_group(default_cmd: str) -> type[TyperGroup]:
    """Create a TyperGroup that rewrites unknown subcommands as args to *default_cmd*."""

    class _FallbackGroup(TyperGroup):
        def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
            try:
                return super().resolve_command(ctx, args)
            except click.UsageError:
                return super().resolve_command(ctx, [default_cmd, *args])

    return _FallbackGroup
