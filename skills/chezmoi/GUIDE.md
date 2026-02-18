# Chezmoi Dotfiles Manager

A practical guide to managing dotfiles with [chezmoi](https://www.chezmoi.io/) — the tool that keeps your configs consistent across machines without the symlink spaghetti.

Chezmoi manages your dotfiles by maintaining a **source state** (a git repo of your desired configs) and applying changes to your **target** (your actual home directory). Unlike GNU Stow or bare git repos, chezmoi doesn't just symlink files — it supports templates, encryption, scripts, and per-machine differences out of the box.

Source state lives in `~/.local/share/chezmoi` by default.

## Setup

### Install

```bash
# macOS
brew install chezmoi

# Linux (one-liner)
sh -c "$(curl -fsLS get.chezmoi.io)"

# Or with mise
mise install chezmoi
```

### Initialize

```bash
# Create a new chezmoi repo
chezmoi init

# Or init from an existing dotfiles repo
chezmoi init https://github.com/username/dotfiles.git
```

This creates `~/.local/share/chezmoi` — your source directory.

### Connect to Git

```bash
chezmoi cd                      # cd into the source directory
git remote add origin <url>
git add .
git commit -m "initial commit"
git push -u origin main
```

### On a New Machine

```bash
# One command to install chezmoi, clone your repo, and apply
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply username
```

## Adding Files

```bash
# Add a single file
chezmoi add ~/.zshrc

# Add a directory
chezmoi add ~/.config/nvim

# Add an entire directory tree
chezmoi add ~/.ssh
```

This copies the files into the source state with the appropriate naming conventions.

## The Naming Convention

This is the core of chezmoi. Files in the source directory use **prefix/suffix attributes** that encode metadata about the target file.

### Prefixes

| Prefix | Effect | Example |
|--------|--------|---------|
| `dot_` | Leading dot in target | `dot_zshrc` → `.zshrc` |
| `private_` | Remove group/world permissions (0600/0700) | `private_dot_ssh` → `.ssh` (mode 700) |
| `readonly_` | Remove write permissions | `readonly_dot_config` |
| `empty_` | Keep file even if empty | `empty_dot_gitconfig` |
| `executable_` | Add execute permission | `executable_dot_local/bin/myscript` |
| `encrypted_` | Encrypted in source state | `encrypted_private_dot_env` |
| `exact_` | Remove unmanaged children | `exact_dot_config/exact_nvim` |
| `symlink_` | Create a symlink (see below) | `symlink_dot_zshrc` |
| `create_` | Only create if doesn't exist | `create_dot_gitconfig` |
| `modify_` | Script that modifies existing file | `modify_dot_gitconfig` |
| `remove_` | Remove the target | `remove_dot_old_config` |
| `run_` | Execute as a script | `run_install-packages.sh` |
| `literal_` | Stop parsing attributes | `literal_dot_file_with_underscores` |

### Suffixes

| Suffix | Effect |
|--------|--------|
| `.tmpl` | Treat as a Go template |
| `.literal` | Stop parsing suffix attributes |

### Prefix Order Matters

Prefixes must appear in a specific order depending on the target type:

- **Regular files:** `encrypted_`, `private_`, `readonly_`, `empty_`, `executable_`, `dot_`
- **Directories:** `remove_`, `external_`, `exact_`, `private_`, `readonly_`, `dot_`
- **Symlinks:** `symlink_`, `dot_`
- **Scripts:** `run_`, `once_` or `onchange_`, `before_` or `after_`

### Examples

```
Source state                          → Target
────────────────────────────────────────────────────────
dot_zshrc                             → ~/.zshrc
dot_config/                           → ~/.config/
private_dot_ssh/                      → ~/.ssh/              (mode 700)
executable_dot_local/bin/myscript     → ~/.local/bin/myscript (mode 755)
private_dot_config/private_Code/      → ~/.config/Code/      (mode 700)
encrypted_private_dot_env             → ~/.env               (decrypted, mode 600)
exact_dot_config/exact_nvim/          → ~/.config/nvim/      (unmanaged files removed)
```

## Symlinks

Chezmoi doesn't use symlinks by default — it copies files. But you can explicitly create symlinks when needed.

### Create a Symlink to a Fixed Path

Create a file with the `symlink_` prefix containing the target path:

```bash
# In the source directory
echo -n "/opt/homebrew/etc/my.cnf" > symlink_dot_my.cnf
```

This creates `~/.my.cnf` → `/opt/homebrew/etc/my.cnf`.

### Symlink with Templates

Use `.tmpl` suffix for dynamic symlink targets:

```bash
# symlink_dot_my.cnf.tmpl
{{ if eq .chezmoi.os "darwin" -}}
/opt/homebrew/etc/my.cnf
{{- else -}}
/etc/mysql/my.cnf
{{- end -}}
```

### Symlink a Directory

Chezmoi symlinks work for directories too. The source file (not directory) contains the path to the target directory:

```bash
# Create a symlink from ~/.config/nvim → ~/dotfiles/nvim
echo -n "{{ .chezmoi.homeDir }}/dotfiles/nvim" > symlink_dot_config/symlink_nvim.tmpl
```

### Symlink Back to Source (for Externally Modified Files)

This is useful for files that programs modify (e.g., VS Code settings). The symlink points back into the chezmoi source directory, so edits go straight into version control:

```bash
# Copy the file to source root
cp ~/.config/Code/User/settings.json $(chezmoi source-path)/

# Ignore it in the normal source tree
echo "settings.json" >> $(chezmoi source-path)/.chezmoiignore

# Create a symlink entry pointing back to source
mkdir -p $(chezmoi source-path)/private_dot_config/private_Code/User
echo -n '{{ .chezmoi.sourceDir }}/settings.json' > \
  $(chezmoi source-path)/private_dot_config/private_Code/User/symlink_settings.json.tmpl
```

### Global Symlink Mode

If you prefer symlinks everywhere (like GNU Stow), set in `~/.config/chezmoi/chezmoi.toml`:

```toml
mode = "symlink"
```

This makes `chezmoi apply` create symlinks instead of copies for regular, non-encrypted, non-template files.

## Templates

Templates use Go's `text/template` syntax and are powerful for per-machine configs.

### Template Data

Chezmoi provides built-in variables:

```
{{ .chezmoi.hostname }}      → machine hostname
{{ .chezmoi.os }}            → "darwin", "linux", etc.
{{ .chezmoi.arch }}          → "amd64", "arm64", etc.
{{ .chezmoi.homeDir }}       → home directory path
{{ .chezmoi.sourceDir }}     → chezmoi source directory
{{ .chezmoi.username }}      → current username
```

### Custom Data

Add your own variables in `~/.config/chezmoi/chezmoi.toml`:

```toml
[data]
    email = "you@example.com"
    name = "Your Name"
    work = false
```

Use them in templates:

```bash
# dot_gitconfig.tmpl
[user]
    name = {{ .name }}
    email = {{ .email }}
{{ if .work }}
[url "git@work-github.com:"]
    insteadOf = https://github.com/
{{ end }}
```

### Conditional Sections

```bash
# dot_zshrc.tmpl
{{ if eq .chezmoi.os "darwin" -}}
export HOMEBREW_PREFIX="/opt/homebrew"
eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"
{{ end -}}

{{ if eq .chezmoi.hostname "workstation" -}}
source ~/.work-env
{{ end -}}
```

### Interactive Prompts

Use `chezmoi init` prompts for first-time setup:

```toml
# .chezmoi.toml.tmpl (in source root)
[data]
    email = {{ promptStringOnce . "email" "What is your email" | quote }}
    work = {{ promptBoolOnce . "work" "Is this a work machine" }}
```

## Scripts

Scripts run actions during `chezmoi apply`. They live in the source directory.

### Types

| Prefix | Behavior |
|--------|----------|
| `run_` | Runs every `chezmoi apply` |
| `run_once_` | Runs once per unique content hash |
| `run_onchange_` | Runs when content changes |

### Ordering

| Prefix | When |
|--------|------|
| `before_` | Before files are updated |
| `after_` | After files are updated |

### Example: Install Packages

```bash
# run_onchange_before_install-packages.sh.tmpl
#!/bin/bash

{{ if eq .chezmoi.os "darwin" -}}
brew bundle --file=/dev/stdin <<EOF
brew "ripgrep"
brew "fd"
brew "mise"
EOF
{{ else if eq .chezmoi.os "linux" -}}
sudo apt install -y ripgrep fd-find
{{ end -}}
```

The `onchange` prefix means it only re-runs when you edit the script (add new packages).

### Script Directory

Put scripts in `.chezmoiscripts/` at the source root to keep them organized without creating a target directory.

## External Sources

Pull files/repos from URLs without committing them to your dotfiles repo.

### `.chezmoiexternal.toml`

```toml
# Oh My Zsh
[".oh-my-zsh"]
    type = "archive"
    url = "https://github.com/ohmyzsh/ohmyzsh/archive/master.tar.gz"
    exact = true
    stripComponents = 1
    refreshPeriod = "168h"

# Single file
[".vim/autoload/plug.vim"]
    type = "file"
    url = "https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim"
    refreshPeriod = "168h"

# Git repo
[".tmux/plugins/tpm"]
    type = "git-repo"
    url = "https://github.com/tmux-plugins/tpm.git"
    refreshPeriod = "168h"
```

Force refresh with:

```bash
chezmoi -R apply
```

## Encryption

Chezmoi supports age and GPG encryption for secrets.

### Setup with age

```toml
# ~/.config/chezmoi/chezmoi.toml
encryption = "age"
[age]
    identity = "~/.config/chezmoi/key.txt"
    recipient = "age1..."
```

### Generate a key

```bash
age-keygen -o ~/.config/chezmoi/key.txt
```

### Add encrypted files

```bash
chezmoi add --encrypt ~/.ssh/id_ed25519
```

This creates `encrypted_private_dot_ssh/encrypted_private_id_ed25519` in source state. The file is encrypted at rest in git but decrypted during `chezmoi apply`.

## Common Workflows

### Day-to-Day

```bash
chezmoi edit ~/.zshrc         # Edit in source state, opens $EDITOR
chezmoi diff                  # Preview what would change
chezmoi apply                 # Apply changes to home directory
chezmoi cd && git add -A && git commit -m "update" && git push
```

### Pull Updates on Another Machine

```bash
chezmoi update                # git pull + apply in one command
```

### See What chezmoi Manages

```bash
chezmoi managed               # List all managed files
chezmoi managed --include dirs # Include directories
chezmoi unmanaged              # List unmanaged files in target dirs
chezmoi cat ~/.zshrc           # Show what chezmoi would write
```

### Dry Run

```bash
chezmoi apply --dry-run --verbose   # See what would happen without doing it
```

### Forget a File

```bash
chezmoi forget ~/.old-config   # Stop managing (removes from source state)
```

## Directory Handling

### Manage an Empty Directory

```bash
mkdir -p $(chezmoi source-path)/dot_local/share/my-app
touch $(chezmoi source-path)/dot_local/share/my-app/.keep
```

The `.keep` file is seen by git but ignored by chezmoi.

### Exact Directories

By default, chezmoi only ensures managed files exist — it won't delete extra files in a directory. Use `exact_` to make chezmoi remove unmanaged files:

```bash
chezmoi chattr exact ~/.config/nvim
```

This renames the source directory to `exact_dot_config/exact_nvim/`, and now `chezmoi apply` will remove any files in `~/.config/nvim/` that aren't in the source state.

⚠️ Be careful with `exact_` — it will delete files. Always `chezmoi apply --dry-run` first.

## Special Files

| File | Purpose |
|------|---------|
| `.chezmoi.toml.tmpl` | Template for config file (for `chezmoi init` prompts) |
| `.chezmoiignore` | Patterns to ignore (supports templates for per-OS ignoring) |
| `.chezmoiremove` | Patterns of files to remove from target |
| `.chezmoiexternal.toml` | External file/archive/repo sources |
| `.chezmoiversion` | Minimum chezmoi version required |
| `.chezmoiscripts/` | Directory for scripts (no target directory created) |
| `.chezmoitemplates/` | Reusable template fragments |

## Quick Reference

```bash
chezmoi init                    # Initialize
chezmoi add <file>              # Start managing a file
chezmoi add --encrypt <file>    # Add encrypted
chezmoi edit <file>             # Edit in source state
chezmoi diff                    # Preview changes
chezmoi apply                   # Apply to home dir
chezmoi apply -v --dry-run      # Preview verbosely
chezmoi update                  # Pull + apply
chezmoi cd                      # cd to source dir
chezmoi managed                 # List managed files
chezmoi forget <file>           # Stop managing
chezmoi chattr <attr> <file>    # Change attributes
chezmoi cat <file>              # Show target contents
chezmoi source-path <file>      # Show source path for a target
chezmoi data                    # Show template data
chezmoi doctor                  # Diagnose problems
```
