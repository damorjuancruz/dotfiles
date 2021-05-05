##### DEPENDENCIES #####
# neovim
# emacs (daemon running)
# powerlevel10k
# fvm
# shell-color-scripts
# zoxide
# fzf
# thefuck

##### RUN COLORSCRIPT ON STARTUP #####
colorscript random

##### SSH #####
SSH_ENV="$HOME/.ssh/agent-environment"

function start_agent {
    echo "Initialising new SSH agent..."
    /usr/bin/ssh-agent | sed 's/^echo/#echo/' > "${SSH_ENV}"
    echo succeeded
    chmod 600 "${SSH_ENV}"
    . "${SSH_ENV}" > /dev/null
    /usr/bin/ssh-add;
}

# Source SSH settings, if applicable

if [ -f "${SSH_ENV}" ]; then
    . "${SSH_ENV}" > /dev/null
    #ps ${SSH_AGENT_PID} doesn't work under cywgin
    ps -ef | grep ${SSH_AGENT_PID} | grep ssh-agent$ > /dev/null || {
        start_agent;
    }
else
    start_agent;
fi

##### POWERLEVEL10K #####
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

##### VARIABLES #####
export TERM=xterm-256color
export EDITOR=nvim
#export VISUAL='emacsclient -c'
export MANPAGER="nvim -c 'set ft=man' -" # "nvim" as manpager

##### ZSH PLUGINS #####
source ~/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh
source ~/.zsh/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh
source ~/.zsh/zsh-command-not-found/command-not-found.plugin.zsh
source ~/.zsh/alias-tips/alias-tips.plugin.zsh
source ~/.zsh/almostontop/almostontop.plugin.zsh
source ~/.zsh/zsh-auto-notify/auto-notify.plugin.zsh
source ~/.zsh/zsh-vi-mode/zsh-vi-mode.plugin.zsh
eval "$(zoxide init zsh)"
eval $(thefuck --alias)

##### ZSH OPTIONS #####
setopt correct
setopt autocd # if a command is issued that can't be executed as a normal command, and the command is the name of a directory, perform the cd command to that directory.
setopt noclobber
setopt noflowcontrol # no c-s/c-q output freezing
setopt prompt_subst # allow expansion in prompts
setopt extended_history # save each command's beginning timestamp and the duration to the history file
setopt longlistjobs # display PID when suspending processes as well
setopt nonomatch # try to avoid the 'zsh: no matches found...'
setopt notify # report the status of backgrounds jobs immediately
setopt hash_list_all # whenever a command completion is attempted, make sure the entire command path is hashed first.
setopt completeinword # not just at the end
setopt noshwordsplit # use zsh style word splitting
setopt interactivecomments # allow use of comments in interactive code
setopt share_history # import new commands from the history file also in other zsh-session
setopt histignorealldups # If a new command line being added to the history list duplicates an older one, the older command is removed from the list
setopt histignorespace # remove command lines from the history list when the first character on the line is a space
typeset -U path cdpath fpath manpath # automatically remove duplicates from these arrays

##### PLUGIN OPTIONS #####
export ZSH_PLUGINS_ALIAS_TIPS_TEXT="💡 "

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
#bindkey -v # Vi mode
bindkey '^ ' autosuggest-accept

##### ALIASES #####
[ -f "$HOME/.zsh/aliasrc" ] && source "$HOME/.zsh/aliasrc"

##### PATH #####
export PATH=~/.emacs.d/bin:$PATH # doom command
export PATH=$PATH:/home/juan/.config/coc/extensions/coc-clangd-data/install/11.0.0/clangd_11.0.0/bin # neoclide/coc.nvim requires this for C/C++

##### BROOT #####
source /home/juan/.config/broot/launcher/bash/br

##### POWERLEVEL10K #####
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
source ~/powerlevel10k/powerlevel10k.zsh-theme
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

##### FNM #####
export PATH=/home/juan/.fnm:$PATH
eval "`fnm env`"
