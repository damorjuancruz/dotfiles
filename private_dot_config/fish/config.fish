if status is-interactive
  ### FISHER ###
  if not functions -q fisher; and status is-interactive
    curl -sL https://git.io/fisher | source && fisher update || fisher install jorgebucaran/fisher
  end

  ### VARIABLES ###
  # nvm
  set --universal nvm_default_version lts/hydrogen
  set --universal nvm_default_packages yarn pnpm

  # catppuccin for fzf
  set -Ux FZF_DEFAULT_OPTS "\
  --color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
  --color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
  --color=marker:#f5e0dc,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8"
  # fix clipboard with tmux + nvim
  set -Ux DISPLAY :1

  ### ALIASES / ABBREVIATIONS / FUNCTIONS ###
  # dotfiles repo
  alias dotfiles "git --git-dir=$HOME/.dotfiles.git/ --work-tree=$HOME"

  # ls -> exa
  alias exa "exa --color=always --group-directories-first --icons --git" # settings
  alias ls "exa -alhg" # alias for ATL + L
  abbr ls "exa -alhg" # my preferred listing
  abbr la "exa -a"  # all files and dirs
  abbr ll "exa -lg"  # long format
  abbr lt "exa -aT" # tree listing

  # cat -> bat
  abbr cat "bat"
  # rm -> trash-cli
  abbr rm "trash"

  # confirm before overwriting something
  abbr cp "cp -i"
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

  # paru
  abbr paru-r "paru -Rns" # remove packages
  abbr paru-c "paru -Rns \$(paru -Qdtq)" # cleanup

  # editors
  abbr v "nvim"

  # git
  abbr g "git"
  abbr gs "git status"
  abbr gl "git log --oneline"
  abbr glg "git graph"
  abbr gll "git log"
  abbr ga "git add"
  abbr gap "git add -p"
  abbr gai "git add -i"
  abbr gaa "git add --all"
  abbr gc "git commit -m"
  abbr gca "git commit -am"
  abbr gac "git add --all && git commit -m"
  abbr gapc "git add -p && git commit -m"
  abbr gaic "git add -i && git commit -m"
  abbr gco "git checkout"
  abbr gcob "git checkout -b"
  abbr gd "git diff"
  abbr gp "git push"
  abbr gpf "git push -f"
  abbr gpl "git pull"

  function gccr
    set BINARY_PATH (mktemp)
    gcc $argv -o $BINARY_PATH && $BINARY_PATH;
    rm $BINARY_PATH;
  end

  function gccm
    set BINARY_PATH (mktemp)
    gcc -Wall $argv -o $BINARY_PATH && valgrind --tool=memcheck $BINARY_PATH;
    rm $BINARY_PATH;
  end

  function update-all --description "Rate mirrors and run a system update"
    set TMPFILE "$(mktemp)";
    sudo true; # ask for the sudo password at the beginning
    rate-mirrors --save=$TMPFILE arch --max-delay=21600 \
      && sudo mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup \
      && sudo mv $TMPFILE /etc/pacman.d/mirrorlist \
      && paru -Scc --noconfirm \
      && paru -Syyu --noconfirm
  end

  ### VI MODE ###
  function fish_user_key_bindings
    fish_vi_key_bindings
    # fish_default_key_bindings
  end

  ### PFETCH ON STARTUP ###
  function fish_greeting
    pfetch
  end

  ### PROMPT ###
  if type -q starship
    starship init fish | source
  else # Autoinstall
    curl -sS https://starship.rs/install.sh | sh && source ~/.config/fish/config.fish
  end
end
