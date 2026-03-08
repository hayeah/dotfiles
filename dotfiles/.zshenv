# Sourced for every zsh session (interactive, non-interactive, login, non-login).

ZSH_INIT_PROFILE=0

# Snapshot pristine PATH for zsh_reload
if [[ -z "$_ORIGINAL_PATH" ]]; then
  export _ORIGINAL_PATH="$PATH"
fi

zmodload zsh/datetime

# Prepend to PATH if directory exists and isn't already present
path_add() {
  [[ -d $1 ]] && [[ :$PATH: != *":$1:"* ]] && PATH="$1:$PATH"
}

# Timed module loader
#
# Modules are loaded by name. _init checks two sources in order:
#   - Function: if _init_<name> is defined, call it
#   - File:     if ~/.zsh_inits/<name> exists, source it
#   - Otherwise print an error
#
# Set ZSH_INIT_PROFILE=1 to print timing to stderr.
#
# To add a new module, create ~/.zsh_inits/<name> (or define _init_<name>).
_init() {
  local name=$1
  local start=$EPOCHREALTIME
  if (( $+functions[_init_$name] )); then
    _init_$name
  elif [[ -f ~/.zsh_inits/$name ]]; then
    source ~/.zsh_inits/$name
  else
    printf '_init: unknown module "%s"\n' "$name" >&2
    return 1
  fi
  local elapsed=$(( (EPOCHREALTIME - start) * 1000 ))
  [[ "$ZSH_INIT_PROFILE" == "1" && -o interactive ]] && printf '  %-20s %5.0fms\n' "$name" "$elapsed" >&2
}

# mise binary lives here — must be in PATH before mise activate
path_add "$HOME/.local/bin"

_init homebrew
_init mise

# Obsidian vault in iCloud
export OB_PATH="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"

# iCloud Drive root
export ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"

# Manga library in iCloud
export MANHUAGUI_ROOT="$ICLOUD_ROOT/manga"

# godzkilla — clone remote skill sources into ~/github.com/... layout
export GODZKILLA_PATH="$HOME"

# gobin — go run shim manager
export GITHUB_REPOS="$HOME"
path_add "$HOME/.gobin/shims"

# Protected sessions for `tm killall` (comma-separated)
export TMUX_KILL_PROTECT="devport"

# hayeah lib config
export HAYEAH_CONFIG="$HOME/.config/hayeah/config.toml"

# Dropbox
export DROPBOX_ROOT="$HOME/Library/CloudStorage/Dropbox"
export MDNOTES_ROOT="$DROPBOX_ROOT/notes"
export OUTPUT_ROOT="$DROPBOX_ROOT/output"
