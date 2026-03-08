"""jsoninspect CLI — pretty-print and colorize JSON with string truncation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from jsoninspect.inspector import JSONInspector, parse_json_objects

app = typer.Typer(
    help="Pretty-print and colorize JSON structure with string truncation.",
    no_args_is_help=True,
)

console = Console(stderr=True)
out = Console()


@app.command()
def main(
    file: Annotated[
        Optional[Path],
        typer.Argument(help="JSON or JSONL file to inspect. Use - for stdin."),
    ] = None,
    max_string: Annotated[
        int,
        typer.Option("--max-string", "-s", help="Max string length before truncation."),
    ] = 80,
    head: Annotated[
        Optional[int],
        typer.Option("--head", help="Only show first N JSON objects."),
    ] = None,
    tail: Annotated[
        Optional[int],
        typer.Option("--tail", help="Only show last N JSON objects."),
    ] = None,
) -> None:
    """Inspect JSON/JSONL files with colorized, truncated output."""
    if file is None or str(file) == "-":
        text = sys.stdin.read()
    else:
        if not file.exists():
            console.print(f"[red]Error:[/red] file not found: {file}")
            raise typer.Exit(1)
        text = file.read_text()

    objects = parse_json_objects(text)

    if not objects:
        console.print("[yellow]No JSON objects found.[/yellow]")
        raise typer.Exit(1)

    # Apply head/tail slicing
    if head is not None:
        objects = objects[:head]
    if tail is not None:
        objects = objects[-tail:]

    inspector = JSONInspector(max_string_length=max_string)
    for i, obj in enumerate(objects):
        if i > 0:
            out.print()
        out.print(inspector.render(obj))
