{ config, pkgs, inputs, ... }:

{
  imports = [ inputs.home-manager.nixosModules.default ];

  home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    extraSpecialArgs = { inherit inputs; };
    users = {
      jcdamor = { config, pkgs, ... }: {
        imports = [
          ../../hm-modules/features/ags.nix
          ../../hm-modules/features/git.nix
          ../../hm-modules/features/ssh.nix
          ../../hm-modules/features/xdg.nix
        ];

        home.username = "jcdamor";
        home.homeDirectory = "/home/jcdamor";

        home.packages = with pkgs; [
          kitty
          neovim
          vesktop
          firefox
          libnotify
          (google-chrome.override {
            commandLineArgs = [
              "--enable-features=WebUIDarkMode"
              "--force-dark-mode"
            ];
          })
          neovide
          fuzzel
          cargo

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
          pfetch
          tldr
          eza
          trash-cli
          unzip
          zip
          wl-clipboard
          ripgrep
          bat
          
          syncthing
          chezmoi

          jq
          fd
          fzf
          nodejs_20
          git
          gcc
          gnumake
          telegram-desktop
          # clang
          cmake
          wget
        ];

        home.sessionVariables = { };

        programs.home-manager.enable = true;
        home.stateVersion = "23.11";
      };
    };
  };
}
