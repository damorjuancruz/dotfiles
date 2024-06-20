{ pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ./home.nix
    ../../os-modules/ssh-agent.nix
    ../../os-modules/hyprland.nix
    ../../os-modules/pipewire.nix
    ../../os-modules/power.nix
    ../../os-modules/plymouth.nix
    ../../os-modules/syncthing.nix
    ../../os-modules/fonts.nix
    ../../os-modules/thunar.nix
    ../../os-modules/bluetooth.nix
  ];

  security.polkit.enable = true;

  hardware.opengl = {
    enable = true;
    extraPackages = with pkgs; [
        intel-media-driver
    ];
  };

  users = {
    mutableUsers = false;

    users.jcdamor = {
      initialPassword = "1234";
      isNormalUser = true;
      description = "Juan Cruz D'Amor";
      extraGroups = [ "networkmanager" "wheel" ];
    };
  };

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    auto-optimise-store = true;
  };

  boot = {
    loader = {
      systemd-boot = {
        enable = true;
        editor = false;
        consoleMode = "max";
      };
      timeout = 0;
      efi.canTouchEfiVariables = true;
    };

    tmp.cleanOnBoot = true;
  };

  networking = {
    hostName = "nixos";
    networkmanager.enable = true;
  };

  time.timeZone = "America/Argentina/Buenos_Aires";

  i18n = {
    defaultLocale = "en_US.UTF-8";
    extraLocaleSettings = {
      LC_ADDRESS = "en_GB.UTF-8";
      LC_IDENTIFICATION = "en_GB.UTF-8";
      LC_MEASUREMENT = "en_GB.UTF-8";
      LC_MONETARY = "en_GB.UTF-8";
      LC_NAME = "en_GB.UTF-8";
      LC_NUMERIC = "en_GB.UTF-8";
      LC_PAPER = "en_GB.UTF-8";
      LC_TELEPHONE = "en_GB.UTF-8";
      LC_TIME = "en_GB.UTF-8";
    };
  };

  nixpkgs.config.allowUnfree = true;

  # This value determines the NixOS release from which the default
  # settings for stateful data, like file locations and database versions
  # on your system were taken. It‘s perfectly fine and recommended to leave
  # this value at the release version of the first install of this system.
  # Before changing this value read the documentation for this option
  # (e.g. man configuration.nix or on https://nixos.org/nixos/options.html).
  system.stateVersion = "23.11"; # Did you read the comment?
}
