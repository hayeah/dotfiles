alias ed='shell-helper editor'
alias project='shell-helper project'

# clone to ~/<host>/<user>/<repo> and cd into it
unalias gg 2>/dev/null
gg() {
    local dest
    dest=$(cd ~ && git-quick-clone "$@") && cd "$dest"
}
