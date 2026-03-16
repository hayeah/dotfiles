"""pydocmd CLI — dump Python API docs as markdown."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

import typer

from . import extract_module_api, module_name_from_path, render_markdown

app = typer.Typer(help="Extract Python API docs as markdown from docstrings.")


def _resolve_target(target: str) -> list[Path]:
    """Resolve a target to source file paths.

    Accepts:
    - A file path (foo.py or path/to/foo.py)
    - A dotted module name (hayeah.imagegen.openai)
    - A directory (extracts all .py files)
    """
    path = Path(target)

    if path.suffix == ".py" and path.exists():
        return [path]

    if path.is_dir():
        return sorted(path.glob("**/*.py"))

    spec = importlib.util.find_spec(target)
    if spec and spec.origin:
        origin = Path(spec.origin)
        if origin.name == "__init__.py":
            return sorted(origin.parent.glob("**/*.py"))
        return [origin]

    typer.echo(f"Error: cannot resolve '{target}' to a Python file or module", err=True)
    raise typer.Exit(1)


@app.command()
def main(
    targets: list[str] = typer.Argument(..., help="Python files, directories, or module names"),
    heading_level: int = typer.Option(2, "--heading-level", "-H", help="Starting heading level"),
    include_private: bool = typer.Option(False, "--private", help="Include _private members"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
) -> None:
    """Extract public API from Python source files as markdown."""
    all_output: list[str] = []

    for target in targets:
        paths = _resolve_target(target)
        if not include_private:
            paths = [p for p in paths if not p.name.startswith("_") or p.name == "__init__.py"]
            paths = [p for p in paths if not p.name.endswith("_test.py")]

        for path in paths:
            api = extract_module_api(path)
            if not api.classes and not api.functions and not api.module_docstring:
                continue

            md = render_markdown(api, heading_level=heading_level)
            if md.strip():
                # Module header when processing multiple files
                if len(paths) > 1 or len(targets) > 1:
                    mod_name = api.module_name or path.name
                    h = "#" * max(1, heading_level - 1)
                    all_output.append(f"{h} {mod_name}\n")
                all_output.append(md)

    result = "\n".join(all_output)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result)
        typer.echo(f"Wrote {output}")
    else:
        sys.stdout.write(result)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
