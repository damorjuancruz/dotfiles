{ lib, config, pkgs, ... }:

{
  systemd.user.services.ssh-agent = {
    description = "SSH key agent";
    environment = {
      SSH_AUTH_SOCK = "%t/ssh-agent.socket";
      DISPLAY = ":0";
    };
    serviceConfig = {
      ExecStart = "${pkgs.openssh}/bin/ssh-agent -D -a $SSH_AUTH_SOCK";
    };
    wantedBy = ["default.target"];
  };

  users = {
    mutableUsers = false;

    users.jcdamor = {
      initialPassword = "1234";
      isNormalUser = true;
      description = "Juan Cruz D'Amor";
      extraGroups = [ "networkmanager" "wheel" ];
      packages = with pkgs; [
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
        clang
        cmake
        wget
      ];
    };
  };
}
