# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# The following lines were added by compinstall

zstyle ':completion:*' completer _complete _ignored _correct _approximate
zstyle :compinstall filename '/home/juan/.zshrc'

autoload -Uz compinit
compinit
# End of lines added by compinstall
# Lines configured by zsh-newuser-install
HISTFILE=~/.histfile
HISTSIZE=1000
SAVEHIST=1000
setopt autocd
unsetopt beep
# End of lines configured by zsh-newuser-install
source ~/powerlevel10k/powerlevel10k.zsh-theme

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Custom aliases
source ~/.aliasrc

# Plugins
# source ~/.zsh/......

# Enviroment Variables
export EDITOR="nvim"

# Show sysfex at startup
sysfex

# fnm
export PATH=/home/juan/.fnm:$PATH
eval "`fnm env`"

[ -f "/home/juan/.ghcup/env" ] && source "/home/juan/.ghcup/env" # ghcup-env

# yarn global
export PATH=/home/juan/.yarn/bin:$PATH
# eval BLITZ_AC_ZSH_SETUP_PATH=/home/juan/.cache/@blitzjs/cli/autocomplete/zsh_setup && test -f $BLITZ_AC_ZSH_SETUP_PATH && source $BLITZ_AC_ZSH_SETUP_PATH; # blitz autocomplete setup
