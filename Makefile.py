"""Makefile.py for dotfiles refresh: stow dotfiles + mise install + skill sync."""

import json
from pathlib import Path

from pymake import sh, task

from dotfile_stow import DotfileStow

HOME = Path.home()
REPO = Path(__file__).resolve().parent
PRIVATE_REPO = HOME / "github.com/hayeah/dotfiles-private"

# Skill sources and destinations for godzkilla sync
SKILL_SOURCES = [
    "github.com/hayeah/dotfiles/skills",
    "github.com/hayeah/devportv2",
    "github.com/hayeah/godzkilla",
    "github.com/hayeah/pymake",
]

SKILL_DESTS = [
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.openclaw/skills",
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
def private(dry: bool = False, force: bool = False):
    """Stow dotfiles-private into ~/.private/ and symlink ~/.env.secret."""
    if not PRIVATE_REPO.exists():
        print("  SKIP dotfiles-private not found")
        return
    stow = DotfileStow(
        source_dir=PRIVATE_REPO,
        target_dir=HOME / ".private",
        config_path=REPO / ".dotfiles.toml",
    )
    stow.apply(dry=dry, force=force)

    # Convenience symlink: ~/.env.secret → ~/.private/.env.secret
    src = HOME / ".private/.env.secret"
    target = HOME / ".env.secret"
    if src.exists() and not target.exists():
        if not dry:
            target.symlink_to(src)
        print(f"  link {target} → {src}")


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
    directives = [{"from": SKILL_SOURCES, "to": SKILL_DESTS}]
    dry_flag = " --dry" if dry else ""

    for dest in [Path(d).expanduser() for d in SKILL_DESTS]:
        if dest.is_symlink():
            dest.unlink()

    sh(f"godzkilla sync{dry_flag} --json '{json.dumps(directives)}'")


@task(inputs=[private, dotfiles, tmux_plugins, mise, skills])
def default():
    """Full refresh: dotfiles + tmux plugins + mise install + sync skills."""
    pass


@task()
def tailscale_acl():
    """Push Tailscale ACL to tailnet."""
    acl = HOME / ".private/tailscale-acl.json"
    if not acl.exists():
        print("  SKIP tailscale-acl.json not found")
        return
    sh(
        "godotenv -f ~/.env.secret sh -c '"
        'curl -s -X POST -H "Authorization: Bearer $TAILSCALE_API_KEY" '
        '-H "Content-Type: application/hujson" '
        f"--data-binary @{acl} "
        "https://api.tailscale.com/api/v2/tailnet/-/acl'"
    )


task.default(default)
