_init p10k
_init antigen
_init fzf
_init zoxide

local ret_status="%(?:%{$fg_bold[green]%}λ :%{$fg_bold[red]%}λ %s)"

PROMPT='${ret_status}%{$fg_bold[green]%}%p %{$fg[cyan]%}${PWD/#$HOME/~} %{$fg_bold[blue]%}$(git_prompt_info)%{$fg_bold[blue]%} % %{$reset_color%}
'

_init bun

_init orbstack

# shell-helper
[ -f ~/github.com/hayeah/dotfiles/skills/shell-helper/helpers.sh ] && source ~/github.com/hayeah/dotfiles/skills/shell-helper/helpers.sh

# Antigravity
path_add "$HOME/.antigravity/antigravity/bin"

zsh_reload() {
  export PATH="$_ORIGINAL_PATH"
  exec zsh -l
}

# Vite+ bin (https://viteplus.dev)
. "$HOME/.vite-plus/env"
