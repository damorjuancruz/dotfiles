if status is-interactive
  ### FISHER ###
  if not functions -q fisher
    curl -sL https://git.io/fisher | source && fisher update || fisher install jorgebucaran/fisher
  end

  ### ALIASES ###
  # dotfiles repo
  alias dotfiles="git --git-dir=$HOME/.dotfiles.git/ --work-tree=$HOME"
  # cd
  alias cd..="cd .."
  # ls -> exa
  alias ls="exa -alhg --color=always --group-directories-first --icons --git" # my preferred listing
  alias la="exa -a --color=always --group-directories-first"  # all files and dirs
  alias ll="exa -lg --color=always --group-directories-first --icons --git"  # long format
  alias lt="exa -aT --color=always --group-directories-first --icons" # tree listing
  # cat -> bat
  alias cat="bat --theme=TwoDark"
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

  alias update-all='export TMPFILE="$(mktemp)"; \
    sudo true; \
    rate-mirrors --save=$TMPFILE arch --max-delay=21600 \
      && sudo mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup \
      && sudo mv $TMPFILE /etc/pacman.d/mirrorlist \
      && paru -Scc --noconfirm \
      && paru -Syyu --noconfirm'

  ### VI MODE ###
  function fish_user_key_bindings
    fish_vi_key_bindings
  end

  ### PFETCH ON STARTUP ###
  function fish_greeting
    pfetch
  end

  ### PROMPT ###
  if type -q starship
    starship init fish | source
  else
    curl -sS https://starship.rs/install.sh | sh && source ~/.config/fish/config.fish
  end
end
