# Install

Assumes [mise](https://mise.jdx.dev/) is already installed.

## Clone the repo

```sh
git clone https://github.com/hayeah/dotfiles ~/github.com/hayeah/dotfiles
```

## Configure template variables

Edit `.dotfiles.toml` in the repo root with your git identity:

```toml
[vars]
gitName = "Your Name"
gitEmail = "you@example.com"
```

## Apply dotfiles

```sh
cd ~/github.com/hayeah/dotfiles
pymake dotfiles --force
```

This symlinks all files from `dotfiles/` into `$HOME`, renders templates (e.g. `.gitconfig`), and creates symlink-file targets. The `--force` flag replaces any existing files on first run.

## Install tools

```sh
mise install
```

Installs the pinned toolchain versions from `~/.config/mise/config.toml`.

## Full refresh

```sh
pymake
```

Runs all tasks: dotfiles + tmux plugins + mise install + skill sync.
