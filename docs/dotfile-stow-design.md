---
overview: Design doc for DotfileStow — a custom pymake "dotfiles" task that symlinks dotfiles with template and symlink-file support, replacing chezmoi.
repo: ~/github.com/hayeah/dotfiles
tags:
  - spec
---

# Chezmoi → Custom Stow Migration Spec

## Goal

Replace `chezmoi apply` with a pymake `dotfiles` task that:

- Symlinks files from `<repo>/dotfiles/` into `$HOME`
- Supports simple template expansion (for the 5 files that need it)
- Requires no `chezmoi` binary at all

All managed dotfiles live under `dotfiles/` in the repo — the repo root stays clean for `Makefile.py`, `skills/`, `AGENTS.md`, etc.

After migration, editing `~/github.com/hayeah/dotfiles/dotfiles/.zshrc` and `~/.zshrc` are the same file — `git diff` works immediately, no apply step.

## Repo Layout (After Migration)

```
~/github.com/hayeah/dotfiles/
├── .dotfiles.toml          ← template variables
├── AGENTS.md
├── Makefile.py
├── README.md
├── dotfile_stow.py         ← DotfileStow helper class
├── dotfile_stow_test.py    ← pytest tests
├── docs/
├── skills/
├── cloudflare/
├── github.com/
└── dotfiles/              ← all managed dotfiles live here
    ├── .zshrc
    ├── .zshenv
    ├── .zprofile
    ├── .p10k.zsh
    ├── .antigen.zsh
    ├── .tmux.conf
    ├── .dmux.global.json
    ├── .gitconfig.tmpl     ← template, rendered to ~/.gitconfig
    ├── .zsh_inits/
    ├── .config/
    ├── .claude/
    │   └── CLAUDE.md.symlink ← symlink, content = target path
    ├── .codex/
    │   └── AGENTS.md.symlink
    └── .openclaw/
        └── CLAUDE.md.symlink
```

## Current Inventory

### Plain files (move `dot_*` → `dotfiles/.*`)

| Chezmoi path | New repo path | Target |
|---|---|---|
| `dot_zshrc` | `dotfiles/.zshrc` | `~/.zshrc` |
| `dot_zshenv` | `dotfiles/.zshenv` | `~/.zshenv` |
| `dot_zprofile` | `dotfiles/.zprofile` | `~/.zprofile` |
| `dot_p10k.zsh` | `dotfiles/.p10k.zsh` | `~/.p10k.zsh` |
| `dot_antigen.zsh` | `dotfiles/.antigen.zsh` | `~/.antigen.zsh` |
| `dot_tmux.conf` | `dotfiles/.tmux.conf` | `~/.tmux.conf` |
| `dot_dmux.global.json` | `dotfiles/.dmux.global.json` | `~/.dmux.global.json` |

### Directories (move `dot_*` → `dotfiles/.*`)

| Chezmoi path | New repo path | Target |
|---|---|---|
| `dot_zsh_inits/` | `dotfiles/.zsh_inits/` | `~/.zsh_inits/` |
| `dot_config/` | `dotfiles/.config/` | `~/.config/` |
| `dot_claude/` | `dotfiles/.claude/` | `~/.claude/` |
| `dot_codex/` | `dotfiles/.codex/` | `~/.codex/` |
| `dot_openclaw/` | `dotfiles/.openclaw/` | `~/.openclaw/` |
| `dot_local/` | `dotfiles/.local/` | `~/.local/` |

### Template files (5 total)

**`dot_gitconfig.tmpl`** → `dotfiles/.gitconfig`
- Variables: `{{ .gitName }}`, `{{ .gitEmail }}`
- Source: `chezmoi.toml` `[data]` section

**`dot_claude/symlink_CLAUDE.md.tmpl`** → `~/.claude/CLAUDE.md` (symlink)
- Content: `{{ .chezmoi.sourceDir }}/AGENTS.md`
- This is a chezmoi-managed symlink pointing to the repo's `AGENTS.md`

**`dot_codex/symlink_AGENTS.md.tmpl`** → `~/.codex/AGENTS.md` (symlink)
- Same pattern, points to `AGENTS.md`

**`dot_openclaw/symlink_CLAUDE.md.tmpl`** → `~/.openclaw/CLAUDE.md` (symlink)
- Same pattern, points to `AGENTS.md`

**`dot_local/share/symlink_chezmoi.tmpl`** → `~/.local/share/chezmoi` (symlink)
- Content: `{{ .chezmoi.homeDir }}/github.com/hayeah/dotfiles`
- Points back to the dotfiles repo itself (may be droppable post-migration)

### External dependency

**`.chezmoiexternal.toml`** — fetches `tmux-sensible` plugin:
```toml
[".tmux/plugins/tmux-sensible"]
    type = "archive"
    url = "https://github.com/tmux-plugins/tmux-sensible/archive/25cb91f42d020f675bb0a2ce3fbd3a5d96119efa.tar.gz"
    stripComponents = 1
```

### Files to delete post-migration

- `.chezmoiignore`
- `.chezmoiexternal.toml`
- `chezmoi.toml.example`

## Migration Plan

### Step — Create `dotfiles/` and move files

```bash
mkdir -p dotfiles

# Plain files
git mv dot_zshrc dotfiles/.zshrc
git mv dot_zshenv dotfiles/.zshenv
git mv dot_zprofile dotfiles/.zprofile
git mv dot_p10k.zsh dotfiles/.p10k.zsh
git mv dot_antigen.zsh dotfiles/.antigen.zsh
git mv dot_tmux.conf dotfiles/.tmux.conf
git mv dot_dmux.global.json dotfiles/.dmux.global.json

# Directories
git mv dot_zsh_inits dotfiles/.zsh_inits
git mv dot_config dotfiles/.config
git mv dot_claude dotfiles/.claude
git mv dot_codex dotfiles/.codex
git mv dot_openclaw dotfiles/.openclaw
git mv dot_local dotfiles/.local
```

### Step — Convert template files

**`dot_gitconfig.tmpl`** → `dotfiles/.gitconfig.tmpl`

Convert from chezmoi `{{ .var }}` syntax to Python `string.Template` `$var` syntax:

```ini
[user]
    name = $gitName
    email = $gitEmail
```

Variables are defined in `.dotfiles.toml` (see below).

**Symlink templates** — convert chezmoi `symlink_*.tmpl` files to `.symlink` files. Each `.symlink` file contains one line: the target path, resolved relative to the `.symlink` file's own directory.

- `dot_claude/symlink_CLAUDE.md.tmpl` → `dotfiles/.claude/CLAUDE.md.symlink` (content: `../../AGENTS.md`)
- `dot_codex/symlink_AGENTS.md.tmpl` → `dotfiles/.codex/AGENTS.md.symlink` (content: `../../AGENTS.md`)
- `dot_openclaw/symlink_CLAUDE.md.tmpl` → `dotfiles/.openclaw/CLAUDE.md.symlink` (content: `../../AGENTS.md`)
- Remove `dotfiles/.local/share/symlink_chezmoi.tmpl` (drop entirely — not needed post-migration)

### Step — Create `.dotfiles.toml`

Config file at `<reporoot>/.dotfiles.toml` defines template variables:

```toml
[vars]
gitName = "Howard Yeh"
gitEmail = "hayeah@gmail.com"
```

- Committed to the repo with real defaults
- Loaded with `tomllib` (stdlib, Python 3.11+)
- Per-machine overrides: add a `.dotfiles.local.toml` (gitignored) that merges on top (optional, only if needed later)

### Step — Handle tmux-sensible

Option A: Git submodule
```bash
git submodule add https://github.com/tmux-plugins/tmux-sensible dotfiles/.tmux/plugins/tmux-sensible
```

Option B: Pymake task to fetch it (simpler)
```python
@task()
def tmux_plugins():
    """Fetch tmux plugins."""
    dest = HOME / ".tmux/plugins/tmux-sensible"
    if not dest.exists():
        sh("git clone https://github.com/tmux-plugins/tmux-sensible " + str(dest))
```

### Step — Write `DotfileStow` helper class

Implement the core logic in a testable `DotfileStow` class, separate from the pymake task. Lives in `dotfile_stow.py` at the repo root.

#### Class design

```python
class DotfileStow:
    """Manages symlinking dotfiles into a target directory."""

    def __init__(self, source_dir: Path, target_dir: Path, config_path: Path):
        """
        source_dir: dotfiles/ directory containing managed files
        target_dir: where symlinks are created (typically $HOME)
        config_path: path to .dotfiles.toml
        """

    def plan(self) -> list[Action]:
        """Compute actions without side effects. Returns list of actions to take."""

    def apply(self, dry: bool = False, force: bool = False):
        """Execute the plan. Print each action. Dry mode prints without acting."""
```

`Action` is a dataclass with a `kind` field:
- `symlink` — create symlink at target pointing to source
- `template` — render template and write to target
- `skip` — target already correct
- `conflict` — target exists and differs (warn unless `--force`)

#### Behavior

The class walks `source_dir` recursively. For each leaf file:

- **Plain file** → create symlink at corresponding `target_dir` path
  - `dotfiles/.zshrc` → symlink `~/.zshrc` → `<repo>/dotfiles/.zshrc`
- **`.tmpl` file** → render with `string.Template` and write (copy) to target, stripping `.tmpl` suffix
  - `dotfiles/.gitconfig.tmpl` → renders to `~/.gitconfig`
  - Missing variables raise `KeyError` — fail loudly
- **`.symlink` file** → read content as target path (relative to the `.symlink` file's own directory), create symlink, stripping `.symlink` suffix
  - `dotfiles/.claude/CLAUDE.md.symlink` (content: `../../AGENTS.md`) → symlink `~/.claude/CLAUDE.md` → `<repo>/AGENTS.md`
  - May use `..` to reference files outside `dotfiles/` but within the repo
  - Paths that resolve outside the repo root are rejected

Rules:
- If the target already exists and is the correct symlink: skip
- If the target exists and is a regular file/dir: warn and skip (or `--force` to overwrite)
- For templates: overwrite the target if content changed
- Create parent dirs as needed

#### Directory symlinking strategy

Always symlink individual leaf files, never whole directories. Create real directories as needed in the target. This keeps non-managed files (written by other tools) out of the repo's git status.

#### Testing

Test with `pytest` using `tmp_path` fixtures — no real `$HOME` needed:

```python
def test_symlink_plain_file(tmp_path):
    source = tmp_path / "dotfiles"
    target = tmp_path / "home"
    source.mkdir(); target.mkdir()
    (source / ".zshrc").write_text("# zshrc")
    config = tmp_path / ".dotfiles.toml"
    config.write_text("[vars]\n")

    stow = DotfileStow(source, target, config)
    stow.apply()

    assert (target / ".zshrc").is_symlink()
    assert (target / ".zshrc").resolve() == (source / ".zshrc").resolve()

def test_template_rendering(tmp_path):
    source = tmp_path / "dotfiles"
    target = tmp_path / "home"
    source.mkdir(); target.mkdir()
    (source / ".gitconfig.tmpl").write_text("[user]\n    name = $gitName\n")
    config = tmp_path / ".dotfiles.toml"
    config.write_text('[vars]\ngitName = "Alice"\n')

    stow = DotfileStow(source, target, config)
    stow.apply()

    result = (target / ".gitconfig").read_text()
    assert "Alice" in result
    assert not (target / ".gitconfig").is_symlink()

def test_skip_existing_correct_symlink(tmp_path): ...
def test_conflict_warns_without_force(tmp_path): ...
def test_force_overwrites_conflict(tmp_path): ...
def test_dry_run_no_side_effects(tmp_path): ...
def test_missing_template_var_raises(tmp_path): ...
def test_nested_dirs_created(tmp_path): ...
def test_symlink_file(tmp_path): ...
```

Run with: `uv run pytest dotfile_stow_test.py`

### Step — Update `Makefile.py`

Replace the `chezmoi` task — thin wrapper around `DotfileStow`:

```python
from dotfile_stow import DotfileStow

REPO = Path(__file__).resolve().parent

@task()
def dotfiles(dry: bool = False, force: bool = False):
    """Symlink dotfiles/ into $HOME."""
    stow = DotfileStow(
        source_dir=REPO / "dotfiles",
        target_dir=HOME,
        config_path=REPO / ".dotfiles.toml",
    )
    stow.apply(dry=dry, force=force)

@task(inputs=[dotfiles, tmux_plugins, mise, skills])
def default():
    """Full refresh: dotfiles + tmux plugins + mise install + sync skills."""
    pass
```

### Step — Clean up

- Remove chezmoi config: `~/.config/chezmoi/chezmoi.toml`
- Remove chezmoi state: `~/.local/share/chezmoi` (currently a symlink to the repo)
- Delete `.chezmoiignore`, `.chezmoiexternal.toml`, `chezmoi.toml.example` from repo
- Optionally uninstall chezmoi: `mise uninstall chezmoi` or `brew uninstall chezmoi`

## Ordering Concern: Dotfiles vs Skills Sync

Currently the `skills` task (godzkilla sync) writes into `~/.claude/skills/`, `~/.codex/skills/`, `~/.openclaw/skills/`. If `.claude/` is symlinked as a whole directory to the repo, then godzkilla writes skill files into the repo — which is probably fine since they're already gitignored, but worth verifying.

The `.symlink` files (e.g. `.claude/CLAUDE.md.symlink`) are processed during the normal walk, so no special ordering is needed — parent dirs are created as needed.

## File Suffix Conventions

| Suffix | Behavior | Target name | Output type |
|---|---|---|---|
| _(none)_ | Symlink source file into `$HOME` | Same as source | Symlink |
| `.tmpl` | Render with `string.Template`, write to target | Suffix stripped | Copied file |
| `.symlink` | Read content as target path (relative to file's own directory), create symlink | Suffix stripped | Symlink |
