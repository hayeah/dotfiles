"""Makefile.py for dotfiles refresh: chezmoi apply + godzkilla skill sync."""

from pathlib import Path

from pymake import sh, task

HOME = Path.home()

# Skill sources: local directories containing SKILL.md files
SKILL_SOURCES = [
    HOME / "github.com/hayeah/dotfiles/skills",
    HOME / "github.com/hayeah/devport",
    HOME / "github.com/hayeah/godzkilla",
]

# Agent skill directories to sync into
SKILL_DESTS = [
    HOME / ".claude/skills",
    HOME / ".codex/skills",
    HOME / ".openclaw/skills",
]


@task()
def chezmoi():
    """Apply chezmoi dotfiles."""
    sh("chezmoi apply")


@task()
def sync_skills():
    """Sync skills from local repos into agent skill directories via godzkilla."""
    sources = " ".join(f"--source {s}" for s in SKILL_SOURCES)
    for dest in SKILL_DESTS:
        # Replace legacy symlink with a real directory
        if dest.is_symlink():
            dest.unlink()

        sh(f"godzkilla sync --destination {dest} {sources}")


@task(inputs=[chezmoi, sync_skills])
def refresh():
    """Full refresh: chezmoi apply + sync skills."""
    pass


task.default(refresh)
