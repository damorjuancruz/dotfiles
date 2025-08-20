{ pkgs, ... }: {
  imports = [
    ./hm-modules/waybar.nix
    ./hm-modules/git.nix
    ./hm-modules/ssh.nix
    ./hm-modules/xdg.nix
    ./hm-modules/cursor.nix
    ./hm-modules/nvim.nix
  ];

  home.username = "jcdamor";
  home.homeDirectory = "/home/jcdamor";

  home.packages = with pkgs; [
    spotify
    protonvpn-gui
    logisim

    corefonts
    sway-contrib.grimshot
    grimblast
    nh
    nix-output-monitor

    networkmanagerapplet
    polkit-kde-agent
    gparted
    remmina

    qmk
    libreoffice

    kitty
    vesktop
    firefox
    libnotify
    google-chrome
    neovide
    fuzzel
    cargo
    beeper

    jetbrains.idea-community

    btop
    shotman

    killall
    alacritty
    tmux
    hyprpaper
    wlsunset
    nwg-bar

    starship
    fish
    fastfetch
    tldr
    eza
    trash-cli
    unzip
    zip
    wl-clipboard
    bat
    brightnessctl

    syncthing
    chezmoi

    jq
    fzf
    nodejs_20
    git
    gnumake
    telegram-desktop
    wget
  ];

  home.sessionVariables = { };

  programs.home-manager.enable = true;

  # same as system.stateVersion
  home.stateVersion = "23.11";
}
