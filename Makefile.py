"""Makefile.py for dotfiles refresh: chezmoi apply + godzkilla skill sync."""

from pathlib import Path

from pymake import sh, task

HOME = Path.home()

# Skill sources: local directories containing SKILL.md files
SKILL_SOURCES = [
    "github.com/hayeah/dotfiles/skills",
    "github.com/hayeah/devport",
    "github.com/hayeah/godzkilla",
    "github.com/hayeah/pymake",
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
def sync_skills(dry: bool = False):
    """Sync skills from local repos into agent skill directories via godzkilla."""
    dests = " ".join(f"--destination {d}" for d in SKILL_DESTS)
    sources = " ".join(f"--source {s}" for s in SKILL_SOURCES)
    dry_flag = " --dry" if dry else ""

    for dest in SKILL_DESTS:
        if dest.is_symlink():
            dest.unlink()

    sh(f"godzkilla sync{dry_flag} {dests} {sources}")


@task(inputs=[chezmoi, sync_skills])
def refresh():
    """Full refresh: chezmoi apply + sync skills."""
    pass


task.default(refresh)
