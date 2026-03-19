"""plist CLI — explore macOS plist preferences."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.text import Text

from hayeah.core.fzfmatch import parse_matcher

from plist_inspect.layers import (
    LAYER_ORDER,
    all_domains,
    domain_from_path,
    domain_paths,
    existing_layers,
    is_file_path,
    read_plist,
    resolve_domain,
)
from plist_inspect.render import render_plist

app = typer.Typer(
    help="Explore macOS plist preferences.",
    no_args_is_help=True,
)

console = Console(stderr=True)
out = Console()


@app.command()
def inspect(
    domain: Annotated[str, typer.Argument(help="Domain name or plist file path.")],
    max_string: Annotated[
        int,
        typer.Option("--max-string", "-s", help="Max string length before truncation."),
    ] = 80,
) -> None:
    """Inspect plist layers for a domain."""
    if is_file_path(domain):
        # Direct file path — just read and render it
        path = Path(domain).expanduser()
        data = read_plist(path)
        if data is None:
            console.print(f"[red]Error:[/red] could not read {path}")
            raise typer.Exit(1)
        out.print(render_plist(data, max_string_length=max_string))
        return

    resolved = resolve_domain(domain)
    paths = domain_paths(domain)
    found_any = False

    for layer_name in LAYER_ORDER:
        path = paths[layer_name]
        if not path.exists():
            continue

        data = read_plist(path)
        if data is None:
            continue

        if found_any:
            out.print()

        # Use ~ shorthand for home directory
        display_path = str(path)
        home = str(Path.home())
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home):]

        header = Text()
        header.append(f"// {layer_name}: {display_path}", style="dim")
        out.print(header)
        out.print(render_plist(data, max_string_length=max_string))
        found_any = True

    if not found_any:
        console.print(f"[yellow]No plist files found for domain:[/yellow] {resolved}")
        raise typer.Exit(1)


@app.command()
def which(
    pattern: Annotated[
        Optional[str],
        typer.Argument(help="Fuzzy pattern to filter domains (fzf syntax)."),
    ] = None,
) -> None:
    """Find domains and show which layer files exist."""
    domains = all_domains()

    if pattern:
        matcher = parse_matcher(pattern)
        domains = matcher.match(domains)

    if not domains:
        console.print("[yellow]No matching domains found.[/yellow]")
        raise typer.Exit(1)

    for i, domain in enumerate(domains):
        if i > 0:
            out.print()

        domain_text = Text(domain, style="bold")
        out.print(domain_text)

        layers = existing_layers(domain)
        for layer_name in LAYER_ORDER:
            if layer_name not in layers:
                continue
            path = layers[layer_name]
            display_path = str(path)
            home = str(Path.home())
            if display_path.startswith(home):
                display_path = "~" + display_path[len(home):]

            line = Text()
            line.append(f"  {layer_name:10s}", style="cyan")
            line.append(display_path, style="dim")
            out.print(line)
