##### DEPENDENCIES #####
# neovim
# emacs (daemon running)
# powerlevel10k
# autojump
# nvm
# shell-color-scripts

##### RUN COLORSCRIPT ON STARTUP #####
colorscript random

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

##### VARIABLES #####
export EDITOR=nvim
export VISUAL='emacsclient -c'
export MANPAGER="nvim -c 'set ft=man' -" # "nvim" as manpager

##### ZSH PLUGINS #####
source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
source /usr/share/autojump/autojump.zsh
source /usr/share/doc/pkgfile/command-not-found.zsh

##### ZSH OPTIONS #####
setopt correct
setopt autocd
setopt noclobber

##### HISTORY #####
HISTSIZE=10000000
SAVEHIST=10000000
HISTFILE=~/.cache/zshhistory
setopt hist_ignore_dups  # Ignore duplication command history list
setopt hist_ignore_space # Ignore when commands starts with space
setopt appendhistory

##### BASIC AUTOCOMPLETION #####
autoload -U compinit
zstyle ':completion:*' menu select
zmodload zsh/complist
compinit
_comp_options+=(globdots) # Include hidden files.

##### CUSTOM ZSH KEYBINDINGS #####
bindkey -v #Vi mode
bindkey '^ ' autosuggest-accept

##### ALIASES #####
[ -f "$HOME/.zsh/aliasrc" ] && source "$HOME/.zsh/aliasrc"

##### PATH #####
export PATH=~/.emacs.d/bin:$PATH #doom command
export PATH=$PATH:/home/juan/.config/coc/extensions/coc-clangd-data/install/11.0.0/clangd_11.0.0/bin # neoclide/coc.nvim requires this for C/C++

##### POWERLEVEL10K #####
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
source ~/powerlevel10k/powerlevel10k.zsh-theme
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

##### BROOT #####
source /home/juan/.config/broot/launcher/bash/br
