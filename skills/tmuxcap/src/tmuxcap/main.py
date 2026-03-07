"""tmuxcap - Capture tmux pane content to various formats."""

from pathlib import Path

import typer

from tmuxcap.capture import capture_pane, pane_size
from tmuxcap.clean import clean_lines
from tmuxcap.render import ANSIRenderer

app = typer.Typer(help="Capture tmux pane content and export as txt, html, svg, png, or jpg. Use .raw for unprocessed output.")

SUPPORTED_EXTENSIONS = {".txt", ".raw", ".html", ".svg", ".png", ".jpg", ".jpeg"}


@app.command()
def main(
    target: str = typer.Option(..., "-t", "--target", help="Tmux target pane (e.g. %42, session:window.pane)"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path (.txt, .raw, .html, .svg, .png, .jpg)"),
) -> None:
    """Capture a tmux pane and save to the specified format."""
    out = Path(output)
    ext = out.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        typer.echo(f"Unsupported format: {ext} (supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))})", err=True)
        raise typer.Exit(1)

    width, _ = pane_size(target)
    ansi_text = capture_pane(target)
    raw = ext == ".raw"

    if not raw:
        ansi_text = clean_lines(ansi_text)

    renderer = ANSIRenderer(ansi_text=ansi_text, width=width)

    if ext in (".txt", ".raw"):
        out.write_text(renderer.plain())
    elif ext == ".html":
        out.write_text(renderer.html())
    elif ext == ".svg":
        out.write_text(renderer.svg())
    elif ext in (".png", ".jpg", ".jpeg"):
        fmt = "jpeg" if ext in (".jpg", ".jpeg") else "png"
        out.write_bytes(renderer.image(fmt))

    typer.echo(f"Saved to {out}")
