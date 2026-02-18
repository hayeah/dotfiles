"""ctrlv - paste iCloud clipboard contents to files."""

from __future__ import annotations

from pathlib import Path

import typer

from .clipboard import ClipboardReader, FileItem, ImageItem, TextItem
from .log import setup_logging
from .writer import ClipboardWriter

app = typer.Typer(help="Paste clipboard contents to files.")


def _item_line(index: int, item: object) -> str:
    if isinstance(item, TextItem):
        preview = item.text[:60].replace("\n", "\\n")
        return f"{index:2}  text: {preview!r}"
    elif isinstance(item, ImageItem):
        return f"{index:2}  image ({item.ext}, {len(item.data):,} bytes)"
    elif isinstance(item, FileItem):
        return f"{index:2}  file: {item.path}"
    return f"{index:2}  unknown"


def _print_items(indexed: list[tuple[int, object]]) -> None:
    for index, item in indexed:
        typer.echo(_item_line(index, item))


@app.command()
def paste(
    output_path: Path = typer.Argument(Path("."), help="Directory to write files into (files go to OUTPUT_PATH/.ctrlv/)"),
    dry_run: bool = typer.Option(False, "--list", "-l", help="List items without pasting"),
    append: bool = typer.Option(False, "--add", "-a", help="Append to .ctrlv/ instead of wiping it"),
) -> None:
    """Paste clipboard contents to OUTPUT_PATH/.ctrlv/ as 1.ext, 2.ext, ..."""
    setup_logging()

    reader = ClipboardReader()
    items = reader.items()

    if not items:
        typer.echo("Clipboard is empty", err=True)
        raise typer.Exit(1)

    if dry_run:
        _print_items(list(enumerate(items, start=1)))
        return

    output_path = output_path.resolve() / ".ctrlv"
    writer = ClipboardWriter(dest_dir=output_path)
    result = writer.write_all(items, append=append)

    _print_items([(wi.index, wi.item) for wi in result.items])


def run() -> None:
    app()


if __name__ == "__main__":
    run()
