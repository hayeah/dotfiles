"""Editor launching with project root detection and zoxide integration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .project import root


def open_editor(
    path: Path | None = None,
    editor: str | None = None,
) -> None:
    """Open an editor at the project root, optionally opening a specific file.

    If path is a file, opens the editor at the project root AND opens the file.
    If path is a directory or None, opens the editor at the project root.
    """
    editor_cmd = editor or os.getenv("CODE_EDITOR", "code")
    target = path or Path.cwd()
    project_root = root(target)

    cmd = [editor_cmd, str(project_root)]
    if target.is_file():
        cmd.append(str(target))

    subprocess.run(cmd, check=True)


def open_editor_project(
    query: str,
    editor: str | None = None,
    interactive: bool = False,
) -> None:
    """Use zoxide to match a query to a project, then open editor there.

    With interactive=True, uses zoxide's fzf-based interactive picker.
    """
    editor_cmd = editor or os.getenv("CODE_EDITOR", "code")

    zoxide_cmd = ["zoxide", "query"]
    if interactive:
        zoxide_cmd.append("-i")
    zoxide_cmd.append(query)

    result = subprocess.run(zoxide_cmd, capture_output=True, text=True, check=True)
    project_path = result.stdout.strip()

    if not project_path:
        raise SystemExit("zoxide: no match found")

    subprocess.run([editor_cmd, project_path], check=True)
