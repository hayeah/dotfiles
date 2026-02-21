alias ed='shell-helper editor'
alias project='shell-helper project'

# tm: tmux session management
#   tm          — fzf project picker (find)
#   tm .        — enter session for cwd
#   tm <path>   — enter session for path
#   tm <cmd>    — subcommands: enter, find, select, rename
tm() {
    if [[ $# -eq 1 && -d "$1" ]]; then
        shell-helper tm enter "$1"
    else
        shell-helper tm "$@"
    fi
}

# gg: clone to ~/<host>/<user>/<repo> and cd into it (shorthand for g qc)
unalias gg 2>/dev/null
gg() {
    if [[ $# -eq 0 || "$1" == "--help" || "$1" == "-h" ]]; then
        git-quick-clone "$@"
    else
        local dest
        dest=$(cd ~ && git-quick-clone "$@") && cd "$dest"
    fi
}

# g: git with subcommand extensions
# g qc <repo> — clone to ~/<host>/<user>/<repo> and cd into it
# g <anything else> — pass through to git
unalias g 2>/dev/null
g() {
    case "$1" in
        qc)
            shift
            if [[ $# -eq 0 || "$1" == "--help" || "$1" == "-h" ]]; then
                git-quick-clone "$@"
            else
                local dest
                dest=$(cd ~ && git-quick-clone "$@") && cd "$dest"
            fi
            ;;
        *)
            git "$@"
            ;;
    esac
}
