ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"
[ ! -d $ZINIT_HOME ] && mkdir -p "$(dirname $ZINIT_HOME)"
[ ! -d $ZINIT_HOME/.git ] && git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"
source "${ZINIT_HOME}/zinit.zsh"

# Env
# Catppuccin Mocha theme
export FZF_DEFAULT_OPTS=" \
--color=bg+:#313244,bg:#1E1E2E,spinner:#F5E0DC,hl:#F38BA8 \
--color=fg:#CDD6F4,header:#F38BA8,info:#CBA6F7,pointer:#F5E0DC \
--color=marker:#B4BEFE,fg+:#CDD6F4,prompt:#CBA6F7,hl+:#F38BA8 \
--color=selected-bg:#45475A \
--color=border:#6C7086,label:#CDD6F4"
export BAT_THEME="Catppuccin Mocha"

# Add in zsh plugins
zinit light zsh-users/zsh-syntax-highlighting
zinit light zsh-users/zsh-completions
zinit light zsh-users/zsh-autosuggestions
zinit light Aloxaf/fzf-tab
zinit light nyoungstudios/zsh-history-on-success

# Add in snippets
zinit snippet OMZP::sudo
zinit snippet OMZP::command-not-found # requires updating the pkgfile db with `pkgfile -u`

# Load completions
autoload -Uz compinit && compinit -d "${ZSH_CACHE_DIR}/.zcompdump"

zinit cdreplay -q

# Keybindings
bindkey -e
bindkey '^p' history-search-backward
bindkey '^n' history-search-forward

# History
HISTSIZE=10000
HISTFILE=~/.zsh_history
SAVEHIST=$HISTSIZE
HISTDUP=erase
setopt appendhistory
setopt sharehistory
setopt hist_ignore_space
setopt hist_ignore_all_dups
setopt hist_save_no_dups
setopt hist_ignore_dups
setopt hist_find_no_dups

export LS_COLORS="$(vivid generate catppuccin-mocha)"

# Completion styling
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu no
zstyle ':completion:*:git-checkout:*' sort false
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'eza --color=always --group-directories-first --icons -a $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'eza --color=always --group-directories-first --icons -a $realpath'
zstyle ':fzf-tab:*' use-fzf-default-opts yes
zstyle ':fzf-tab:*' fzf-command ftb-tmux-popup

# Shell integrations
eval "$(fzf --zsh)"
eval "$(zoxide init --cmd cd zsh)"
eval "$(fnm env --use-on-cd --version-file-strategy=recursive --resolve-engines --shell zsh)"

# Aliases
alias eza="eza --color=always --group-directories-first --icons --git" # settings
alias ls="eza -alhg" # preferred listing
alias lt="eza -aT" # tree listing
alias v='nvim'
alias cat='bat'
alias rm='trash'
alias cp="cp -ir" # confirm before overwriting something & recursive copy
alias mv="mv -i"
alias mkdir="mkdir -p" # full path
alias du="du -hs" # print only one, human-readable, total for each argument
alias free="free -h" # human readable
alias less="less -MNi" # file info/position, line number, smart case for searching
alias paru-r="paru -Rns" # remove packages
alias paru-c="paru -Rns \$(paru -Qdtq)" # cleanup

# Sesh
if [[ -z "$TMUX" ]]; then
  # Keybind
  function sesh-sessions() {
    exec </dev/tty
    exec <&1
    local session
    session=$(~/.config/sesh/picker.sh -p)
    zle reset-prompt > /dev/null 2>&1 || true
    [[ -z "$session" ]] && return
    sesh connect $session
  }
  zle -N sesh-sessions
  bindkey -M emacs '^o' sesh-sessions
  bindkey -M vicmd '^o' sesh-sessions
  bindkey -M viins '^o' sesh-sessions

  # Autorun
  local session
  session=$(~/.config/sesh/picker.sh -p)
  if [[ -n "$session" ]]; then
    exec sesh connect $session
  fi
fi

# Prompt
eval "$(starship init zsh)"
