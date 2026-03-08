---
name: dotfiles
description: Personal dev environment — dotfile management, tool pinning, shell config, and 20+ AI agent skills, all orchestrated via pymake.
---

# dotfiles

Personal development environment for macOS. Manages shell configuration, tool versions, git setup, and AI agent skills across Claude, Codex, and OpenClaw.

See [INSTALL.md](INSTALL.md) for setup instructions.

## Architecture

```
dotfiles/              Managed dotfiles (symlinked to $HOME)
  .zshrc, .zshenv      Shell config
  .zsh_inits/           Modular shell init (antigen, fzf, zoxide, p10k, etc.)
  .tmux.conf            tmux config
  .gitconfig.tmpl       Git config (templated with .dotfiles.toml vars)
  .config/mise/         Tool version pinning
  .claude/, .codex/     Agent configs (CLAUDE.md symlinks to AGENTS.md)
skills/                20+ reusable agent skills
hayeah/                Shared Python package (structlog logging)
Makefile.py            pymake orchestration
dotfile_stow.py        Custom symlink manager
.dotfiles.toml         Template variables (gitName, gitEmail)
AGENTS.md              Master AI agent instructions (symlinked into all agent configs)
```

## DotfileStow — Dotfile Manager

Custom lightweight alternative to chezmoi. Files in `dotfiles/` are processed by convention:

- **Plain files** — Symlinked directly to `$HOME` (e.g. `dotfiles/.zshrc` -> `~/.zshrc`)
- **`.tmpl` files** — Rendered via `string.Template` substitution, then written (e.g. `.gitconfig.tmpl` -> `~/.gitconfig`)
  - Variables come from `.dotfiles.toml` `[vars]` section
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

## pymake Tasks

`Makefile.py` defines the full refresh pipeline:

```bash
# Full refresh: dotfiles + tmux plugins + mise install + skill sync
pymake

# Individual tasks
pymake dotfiles              # Symlink dotfiles into $HOME
pymake dotfiles --vars dotfiles.force=true  # Force-overwrite conflicts
pymake tmux_plugins          # Clone tmux-sensible if missing
pymake mise                  # Install pinned tools
pymake skills                # Sync skills to agent directories
pymake skills --vars skills.dry=true  # Preview skill sync
```

The `default` task runs all of the above in sequence.

## Skill Sync

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

## Shell Configuration

Zsh init is split across three files by shell type:

- `.zshenv` — All shells. Sets PATH, env vars, activates mise.
- `.zprofile` — Login shells only. Language toolchain paths (Go, Rust, etc.).
- `.zshrc` — Interactive shells. Loads modules, aliases, prompt.

### Module Loading

`.zshrc` uses a timed `_init` function that sources `~/.zsh_inits/<name>` files:

```
Modules: p10k, antigen, fzf, zoxide, bun, orbstack
```

### Key Environment Variables

```bash
GITHUB_REPOS=~                   # git-quick-clone resolves repos under ~/
GODZKILLA_PATH=~                 # godzkilla resolves repos under ~/
DROPBOX_ROOT=~/Dropbox           # Cloud storage root
MDNOTES_ROOT=$DROPBOX_ROOT/md    # Markdown notes
OUTPUT_ROOT=$DROPBOX_ROOT/output # Task output artifacts
```

### Git Aliases (from .gitconfig.tmpl)

Extensive shorthand aliases — highlights:

```
s = status           c = commit            b = branch
co = checkout        com = checkout master  l = log (pretty)
p = push             po = push origin       pom = push origin master
ap = add -p          ai = add --interactive
ca = commit --amend  cam = commit -am
z = rebase           zc = rebase --continue
rhom = reset --hard origin/master
```

## Tool Management (mise)

Pinned tools in `.config/mise/config.toml`:

```
bat, bun, duckdb, fd, fzf, gh, go, godotenv, mise, neovim,
node, pnpm, python, tmux, uv, zoxide, cloudflared, foundry
```

Run `mise install` (or `pymake mise`) to install all pinned versions.

## Agent Configuration

`AGENTS.md` is the master instruction file for AI agents. It's symlinked into:
- `~/.claude/CLAUDE.md` (via `dotfiles/.claude/CLAUDE.md.symlink`)
- `~/.codex/AGENTS.md`
- `~/.openclaw/AGENTS.md`

Key agent conventions from AGENTS.md:
- Use `uv` + Python for ad-hoc scripting
- Secrets in `~/.env.secret` — agents must never read this directly
- Use `godotenv -o -f ~/.env.secret,.env` to load secrets
- Output artifacts go to `$OUTPUT_ROOT/<date>/<taskName>`
- Default git branch is `master`
- Repos live at `~/github.com/<user>/<repo>`

## Shared Python Package (hayeah)

The `hayeah/` directory provides `hayeah.logger` — structured logging with:
- Colored console output (stderr, TTY-aware)
- JSONL file logging to `~/.local/log/<tool>.jsonl` (5MB rotation, 3 backups)
- `LOG_LEVEL` env var for verbosity control

Skills reference it as an editable dependency:
```toml
hayeah = { path = "../../hayeah", editable = true }
```

## Skills

- **[browser](skills/browser/)** — Interactive browser automation via Chrome DevTools Protocol
- **[chezmoi](skills/chezmoi/)** — Chezmoi reference guide
- **[cloudflare-tunnel](skills/cloudflare-tunnel/)** — Manage Cloudflare Tunnel ingress rules and DNS
- **[ctrlv](skills/ctrlv/)** — Save macOS clipboard contents to `.ctrlv/` subdirectory
- **[dotenv-ls](skills/dotenv-ls/)** — List env var names from .env files without exposing values
- **[dotfiles](skills/dotfiles/)** — DotfileStow system documentation
- **[git-quick-clone](skills/git-quick-clone/)** — Clone GitHub repos with treeless partial clone
- **[gobin](skills/gobin/)** — Install Go packages as editable binaries (like `uv tool install -e`)
- **[golang](skills/golang/)** — Go style guide
- **[imagegen](skills/imagegen/)** — AI image generation with OpenAI and Gemini providers
- **[jsoninspect](skills/jsoninspect/)** — Pretty-print and colorize JSON/JSONL with string truncation
- **[mdnote](skills/mdnote/)** — Create markdown notes in $MDNOTES_ROOT
- **[python](skills/python/)** — Python coding conventions, style guide, and uv tooling
- **[readme-skill](skills/readme-skill/)** — Generate agent-friendly README/SKILL.md
- **[resend](skills/resend/)** — Send emails via Resend API
- **[shell-helper](skills/shell-helper/)** — Project root detection, editor launching, tmux integration
- **[text-copyedit](skills/text-copyedit/)** — Copy-edit text, fix grammar, format as listicles
- **[tmuxcap](skills/tmuxcap/)** — Capture tmux pane as text, HTML, SVG, PNG, or JPG
- **[typescript](skills/typescript/)** — TypeScript tooling and style guide
