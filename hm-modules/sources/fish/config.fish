if status is-interactive
    ### FISHER ###
    if not functions -q fisher; and status is-interactive
        curl -sL https://git.io/fisher | source && fisher update || fisher install jorgebucaran/fisher
    end

    shotman_completions fish | source
    nh completions fish | source

    fish_config theme choose "Catppuccin Mocha"

    # catppuccin for fzf
    set -x FZF_DEFAULT_OPTS "\
--color=bg+:#313244,bg:#1E1E2E,spinner:#F5E0DC,hl:#F38BA8 \
--color=fg:#CDD6F4,header:#F38BA8,info:#CBA6F7,pointer:#F5E0DC \
--color=marker:#B4BEFE,fg+:#CDD6F4,prompt:#CBA6F7,hl+:#F38BA8 \
--color=selected-bg:#45475A \
--color=border:#6C7086,label:#CDD6F4"

    # fix clipboard with tmux + nvim
    set -x DISPLAY :1

    # for nh utility
    set -x NH_FLAKE "$HOME/dotfiles"

    ### ALIASES / ABBREVIATIONS ###

    # zoxide
    zoxide init fish | source
    alias cd z

    # ls -> eza
    alias eza "eza --color=always --group-directories-first --icons --git" # settings
    alias ls "eza -alhg" # alias for ATL + L
    abbr ls "eza -alhg" # my preferred listing
    abbr lt "eza -aT" # tree listing

    # cat -> bat
    abbr cat bat
    # rm -> trash-cli
    abbr rm trash

    # confirm before overwriting something & recursive copy
    abbr cp "cp -ir"
    abbr mv "mv -i"
    # mkdir make full path
    abbr mkdir "mkdir -p"
    # print only one, human-readable, total for each argument
    abbr du "du -hs"
    # human readable
    abbr free "free -h"
    # file info/position, line number, smart case for searching
    alias less "less -MNi" # alias for ALT + P
    abbr less "less -MNi"

    # editors
    abbr v nvim

    ### VI MODE ###
    function fish_user_key_bindings
        fish_vi_key_bindings
    end
    set -g fish_cursor_default block
    set -g fish_cursor_insert line

    # Remove default greeting
    function fish_greeting
    end

    ### PROMPT ###
    if type -q starship
        starship init fish | source
    end

    bind -M default ctrl-o "~/.config/sesh/run.sh"
    bind -M insert ctrl-o "~/.config/sesh/run.sh"

    if not set -q TMUX
        ~/.config/sesh/run.sh
    end
end
