"""Makefile.py for dotfiles refresh: stow dotfiles + mise install + skill sync."""

from pathlib import Path

from pymake import sh, task

from dotfile_stow import DotfileStow

HOME = Path.home()
REPO = Path(__file__).resolve().parent

# Skill sources: local directories containing SKILL.md files
SKILL_SOURCES = [
    "github.com/hayeah/dotfiles/skills",
    "github.com/hayeah/devportv2",
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
def dotfiles(dry: bool = False, force: bool = False):
    """Symlink dotfiles/ into $HOME."""
    stow = DotfileStow(
        source_dir=REPO / "dotfiles",
        target_dir=HOME,
        config_path=REPO / ".dotfiles.toml",
    )
    stow.apply(dry=dry, force=force)


@task()
def tmux_plugins():
    """Fetch tmux plugins."""
    dest = HOME / ".tmux/plugins/tmux-sensible"
    if not dest.exists():
        sh("git clone https://github.com/tmux-plugins/tmux-sensible " + str(dest))


@task()
def mise():
    """Install tools via mise."""
    sh("mise install")


@task()
def skills(dry: bool = False):
    """Sync skills from local repos into agent skill directories via godzkilla."""
    dests = " ".join(f"--destination {d}" for d in SKILL_DESTS)
    sources = " ".join(f"--source {s}" for s in SKILL_SOURCES)
    dry_flag = " --dry" if dry else ""

    for dest in SKILL_DESTS:
        if dest.is_symlink():
            dest.unlink()

    sh(f"godzkilla sync{dry_flag} {dests} {sources}")


@task(inputs=[dotfiles, tmux_plugins, mise, skills])
def default():
    """Full refresh: dotfiles + tmux plugins + mise install + sync skills."""
    pass


task.default(default)
