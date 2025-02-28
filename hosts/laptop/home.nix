{ config, pkgs, inputs, ... }:

{
  imports = [ inputs.home-manager.nixosModules.default ];

  home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    extraSpecialArgs = {
      inherit inputs;
    };
    users = {
      jcdamor = { config, pkgs, ... }: {
        imports = [
          ../../hm-modules/features/ags.nix
          ../../hm-modules/features/git.nix
          ../../hm-modules/features/ssh.nix
          ../../hm-modules/features/xdg.nix
          # ../../hm-modules/features/gtk.nix
          ../../hm-modules/features/cursor.nix
          ../../hm-modules/features/nvim.nix
        ];

        home.username = "jcdamor";
        home.homeDirectory = "/home/jcdamor";

        home.packages = with pkgs; [
          spotify

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
        home.stateVersion = "23.11";
      };
    };
  };
}
