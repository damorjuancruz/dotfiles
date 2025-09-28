{ pkgs, ... }:
{
  imports = [
    ./hm-modules/options.nix
    ./hm-modules/hyprpanel.nix
    ./hm-modules/git.nix
    ./hm-modules/ssh.nix
    ./hm-modules/xdg.nix
    ./hm-modules/cursor.nix
    ./hm-modules/nvim.nix
    ./hm-modules/tmux.nix
    ./hm-modules/ghostty.nix
    ./hm-modules/fish.nix
    ./hm-modules/hyprland.nix
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
    kdePackages.polkit-kde-agent-1
    gparted
    remmina

    qmk
    libreoffice

    kitty
    vesktop
    firefox
    libnotify
    google-chrome
    fuzzel
    cargo
    beeper

    jetbrains.idea-community

    btop
    shotman

    killall
    wlsunset
    nwg-bar

    tldr
    unzip
    zip
    wl-clipboard
    brightnessctl

    syncthing
    chezmoi

    jq
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
