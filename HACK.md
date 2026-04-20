# Hacking on the dotfiles

Plumbing details for editing the repo itself. Most agents loading `README.md` as context for the user's tool universe won't need this — it's the read-if-you're-changing-the-setup tier.

- [Install](#install) — first-time setup
- [Architecture](#architecture) — repo layout
- [DotfileStow](#dotfilestow) — how `dotfiles/` becomes `$HOME`
- [pymake tasks](#pymake-tasks) — full-refresh pipeline
- [Skill sync](#skill-sync) — godzkilla sources and destinations
- [Shell configuration](#shell-configuration) — zshenv/zprofile/zshrc split, key env vars
- [Git aliases](#git-aliases) — shorthand from `.gitconfig.tmpl`
- [Tool management (mise)](#tool-management-mise) — pinned tools
- [Agent configuration](#agent-configuration) — how `AGENTS.md` reaches each agent

## Install

Assumes [mise](https://mise.jdx.dev/) is already installed.

Clone the repo:

```sh
git clone https://github.com/hayeah/dotfiles ~/github.com/hayeah/dotfiles
```

Edit `.dotfiles.toml` in the repo root with your git identity:

```toml
[vars]
gitName = "Your Name"
gitEmail = "you@example.com"
```

Apply dotfiles — `--force` replaces any existing files on first run:

```sh
cd ~/github.com/hayeah/dotfiles
pymake dotfiles --vars dotfiles.force=true
```

This symlinks all files from `dotfiles/` into `$HOME`, renders templates (e.g. `.gitconfig`), and creates symlink-file targets.

Install the pinned toolchain:

```sh
mise install
```

Or run everything (dotfiles + tmux plugins + mise install + skill sync) in one go:

```sh
pymake
```

## Architecture

```
dotfiles/              Managed dotfiles (symlinked to $HOME)
  .zshrc, .zshenv      Shell config
  .zsh_inits/          Modular shell init (antigen, fzf, zoxide, p10k, etc.)
  .tmux.conf           tmux config
  .gitconfig.tmpl      Git config (templated with .dotfiles.toml vars)
  .config/mise/        Tool version pinning
  .claude/, .codex/    Agent configs (CLAUDE.md symlinks to AGENTS.md)
skills/                20+ reusable agent skills
libs/                  Cross-language convention libraries (Python, TS, Go)
docs/                  Durable design specs
Makefile.py            pymake orchestration
dotfile_stow.py        Custom symlink manager
.dotfiles.toml         Template variables (gitName, gitEmail)
AGENTS.md              Master AI agent instructions (symlinked into all agent configs)
```

## DotfileStow

Custom lightweight alternative to chezmoi. Files in `dotfiles/` are processed by convention:

- **Plain files** — Symlinked directly to `$HOME` (e.g. `dotfiles/.zshrc` -> `~/.zshrc`)
- **`.tmpl` files** — Rendered via `string.Template` substitution, then written (e.g. `.gitconfig.tmpl` -> `~/.gitconfig`). Variables come from `.dotfiles.toml` `[vars]` section.
- **`.symlink` files** — Content is read as a relative symlink target (e.g. `CLAUDE.md.symlink` containing `../../AGENTS.md`)

```bash
# Apply dotfiles (dry run)
pymake dotfiles --vars dotfiles.dry=true

# Apply dotfiles (first time — overwrite existing)
pymake dotfiles --vars dotfiles.force=true

# Apply dotfiles (incremental — skips conflicts)
pymake dotfiles
```

Conflict handling: if a target already exists and doesn't match, DotfileStow prints `SKIP` unless `--force` is set.

-> [spec](docs/dotfile-stow-design.md) | [skill](skills/dotfiles/SKILL.md)

## pymake tasks

`Makefile.py` defines the full refresh pipeline:

```bash
# Full refresh: dotfiles + tmux plugins + mise install + skill sync
pymake

# Individual tasks
pymake dotfiles                              # Symlink dotfiles into $HOME
pymake dotfiles --vars dotfiles.force=true   # Force-overwrite conflicts
pymake tmux_plugins                          # Clone tmux-sensible if missing
pymake mise                                  # Install pinned tools
pymake skills                                # Sync skills to agent directories
pymake skills --vars skills.dry=true         # Preview skill sync
```

The `default` task runs all of the above in sequence.

## Skill sync

Skills are synced from multiple source repos into agent-specific directories via [godzkilla](https://github.com/hayeah/godzkilla):

**Sources:**
- `github.com/hayeah/dotfiles/skills` — main skill collection
- `github.com/hayeah/devport` — dev service management
- `github.com/hayeah/godzkilla` — skill manager itself
- `github.com/hayeah/pymake` — build tool

**Destinations:**
- `~/.claude/skills/`
- `~/.codex/skills/`
- `~/.openclaw/skills/`

## Shell configuration

Zsh init is split across three files by shell type:

- `.zshenv` — All shells. Sets PATH, env vars, activates mise.
- `.zprofile` — Login shells only. Language toolchain paths (Go, Rust, etc.).
- `.zshrc` — Interactive shells. Loads modules via a timed `_init` function that sources `~/.zsh_inits/<name>` (p10k, antigen, fzf, zoxide, bun, orbstack).

Key environment variables set in `.zshenv`:

```bash
GITHUB_REPOS=~                   # git-quick-clone resolves repos under ~/
GODZKILLA_PATH=~                 # godzkilla resolves repos under ~/
DROPBOX_ROOT=~/Dropbox           # Cloud storage root
MDNOTES_ROOT=$DROPBOX_ROOT/notes # Markdown notes
OUTPUT_ROOT=$DROPBOX_ROOT/output # Task output artifacts
```

-> [dotfiles/.zshrc](dotfiles/.zshrc) | [dotfiles/.zshenv](dotfiles/.zshenv) | [dotfiles/.zsh_inits/](dotfiles/.zsh_inits/)

## Git aliases

Extensive shorthand from `.gitconfig.tmpl` — highlights:

```
s = status           c = commit            b = branch
co = checkout        com = checkout master  l = log (pretty)
p = push             po = push origin       pom = push origin master
ap = add -p          ai = add --interactive
ca = commit --amend  cam = commit -am
z = rebase           zc = rebase --continue
rhom = reset --hard origin/master
```

-> [dotfiles/.gitconfig.tmpl](dotfiles/.gitconfig.tmpl)

## Tool management (mise)

Pinned tools in `dotfiles/.config/mise/config.toml`:

```
bat, bun, duckdb, fd, fzf, gh, go, godotenv, mise, neovim,
node, pnpm, python, tmux, uv, zoxide, cloudflared, foundry
```

Run `mise install` (or `pymake mise`) to install all pinned versions.

-> [dotfiles/.config/mise/config.toml](dotfiles/.config/mise/config.toml)

## Agent configuration

`AGENTS.md` is the master instruction file for AI agents. It's symlinked into `~/.claude/CLAUDE.md` (via `dotfiles/.claude/CLAUDE.md.symlink`), `~/.codex/AGENTS.md`, and `~/.openclaw/AGENTS.md`.

Key conventions from `AGENTS.md`:
- Use `uv` + Python for ad-hoc scripting
- Secrets in `~/.env.secret` — agents must never read this directly
- Use `godotenv -o -f ~/.env.secret,.env` to load secrets
- Output artifacts go to `$OUTPUT_ROOT/<date>/<taskName>`
- Default git branch is `master`
- Repos live at `~/github.com/<user>/<repo>`

-> [AGENTS.md](AGENTS.md)
