if status is-interactive
  ### ALIASES ###
  # dotfiles repo
  alias dotfiles="/usr/bin/git --git-dir=$HOME/.dotfiles.git/ --work-tree=$HOME"
  # cd
  alias cd..="cd .."
  # ls -> exa
  alias ls="exa -alhg --color=always --group-directories-first --icons --git" # my preferred listing
  alias la="exa -a --color=always --group-directories-first"  # all files and dirs
  alias ll="exa -lg --color=always --group-directories-first --icons --git"  # long format
  alias lt="exa -aT --color=always --group-directories-first --icons" # tree listing
  # cat -> bat
  alias cat="bat"
  # confirm before overwriting something
  alias cp="cp -i"
  alias mv="mv -i"
  # paru
  alias paru-r="paru -Rns"
  alias paru-c="paru -Rns \$(paru -Qdtq)" # cleanup
  # trash-cli
  alias rm="trash"
  # copy file content
  alias copy="xclip -sel clip"

  ### PFETCH ON STARTUP ###
  function fish_greeting
    pfetch
  end

  ### PROMPT ###
  starship init fish | source
end
