"""mdnote — list and browse markdown notes from $MDNOTES_ROOT."""

from __future__ import annotations

import os
import re
from pathlib import Path

import typer

app = typer.Typer(help="Browse markdown notes.")


def _notes_root() -> Path:
    root = os.environ.get("MDNOTES_ROOT")
    if not root:
        typer.echo("MDNOTES_ROOT is not set", err=True)
        raise typer.Exit(1)
    p = Path(root)
    if not p.is_dir():
        typer.echo(f"MDNOTES_ROOT does not exist: {p}", err=True)
        raise typer.Exit(1)
    return p


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_OVERVIEW_RE = re.compile(r"^overview:\s*(.+)$", re.MULTILINE)


def _extract_overview(path: Path) -> str | None:
    """Extract overview from YAML frontmatter without a YAML dependency."""
    try:
        text = path.read_text(errors="replace")[:4096]
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm = m.group(1)
    om = _OVERVIEW_RE.search(fm)
    if not om:
        return None
    val = om.group(1).strip()
    # Handle quoted strings
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        val = val[1:-1]
    return val


@app.command("ls")
def ls(
    date: str | None = typer.Argument(None, help="Date folder to list (e.g. 2026-03-11). Default: all."),
) -> None:
    """List notes and their overview summaries."""
    root = _notes_root()

    if date:
        folders = [root / date]
        if not folders[0].is_dir():
            typer.echo(f"No notes folder for date: {date}", err=True)
            raise typer.Exit(1)
    else:
        folders = sorted(
            [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")],
        )

    for folder in folders:
        notes = sorted(folder.glob("*.md"))
        if not notes:
            continue
        for note in notes:
            rel = f"{folder.name}/{note.name}"
            overview = _extract_overview(note)
            if overview:
                typer.echo(f"{rel}\n  {overview}")
            else:
                typer.echo(rel)
