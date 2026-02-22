"""Shared fzf utilities for interactive project selection."""

from __future__ import annotations

import os
import shlex
import subprocess
from itertools import zip_longest


def fzf_version() -> str | None:
    """Detect installed fzf version string."""
    try:
        r = subprocess.run(["fzf", "--version"], capture_output=True, text=True, check=True)
        return r.stdout.strip().split()[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def version_gte(actual: str, minimum: str) -> bool:
    """Semver comparison: actual >= minimum."""

    def parts(v: str) -> list[int]:
        return [int(x) for x in v.split(".")]

    a, b = parts(actual), parts(minimum)
    for x, y in zip_longest(a, b, fillvalue=0):
        if x != y:
            return x > y
    return True


def build_border_opts(
    fzf_ver: str, list_label: str = "Projects", preview_label: str = "Preview",
) -> str:
    """Build fzf border options based on version (0.58+/0.61+)."""
    opts = ""
    if version_gte(fzf_ver, "0.58.0"):
        opts += (
            f"--input-border --input-label ' Search ' --info=inline-right "
            f"--list-border --list-label ' {list_label} ' "
            f"--preview-border --preview-label ' {preview_label} ' "
        )
    if version_gte(fzf_ver, "0.61.0"):
        opts += "--ghost 'type to search...' "
    return opts or "--preview-label='preview'"


def in_tmux() -> bool:
    """Check whether we're running inside tmux."""
    return bool(os.environ.get("TMUX"))


def select_project(
    projects: list[tuple[str, str]],
    query: str | None = None,
    *,
    list_label: str = "Projects",
    preview_label: str = "Files",
    preview_cmd: str | None = None,
) -> tuple[str, str] | None:
    """Run fzf over (label, path) pairs, return selected pair or None.

    preview_cmd receives {} as the label placeholder.
    """
    fzf_ver = fzf_version()
    if not fzf_ver:
        return None

    border_opts = build_border_opts(fzf_ver, list_label=list_label, preview_label=preview_label)

    fzf_input = "\n".join(label for label, _ in projects)
    lookup = {label: path for label, path in projects}

    tmux_opts = "--tmux center,50%,50% " if in_tmux() else ""
    query_opt = f"--query {shlex.quote(query)} " if query else ""
    preview_opt = (
        f"--preview {shlex.quote(preview_cmd)} --preview-window=right,40%,nowrap "
        if preview_cmd
        else ""
    )

    fzf_cmd = (
        f"fzf --exit-0 --reverse "
        f"{tmux_opts}"
        f"{query_opt}"
        f"{border_opts} "
        f"{preview_opt}"
    )

    try:
        r = subprocess.run(
            fzf_cmd, shell=True, input=fzf_input, capture_output=True, text=True, check=True,
        )
        selected = r.stdout.strip()
    except subprocess.CalledProcessError:
        return None

    if not selected or selected not in lookup:
        return None

    return (selected, lookup[selected])
