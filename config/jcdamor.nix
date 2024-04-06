{ config, pkgs, ... }:

{
  imports = [
    # ./modules/hyprland.nix
    ./modules/ags.nix
    ./modules/git.nix
    ./modules/ssh.nix
  ];

  home.username = "jcdamor";
  home.homeDirectory = "/home/jcdamor";
  xdg.enable = true;
  xdg.userDirs = {
    enable = true;
    createDirectories = true;
    desktop = "${config.home.homeDirectory}/desktop";
    documents = "${config.home.homeDirectory}/documents";
    download = "${config.home.homeDirectory}/downloads";
    pictures = "${config.home.homeDirectory}/pictures";
    extraConfig.XDG_SCREENSHOTS_DIR = "${config.home.homeDirectory}/pictures/screenshots";
    videos = "${config.home.homeDirectory}/videos";
    music = "${config.home.homeDirectory}/xdg-dirs/music";
    publicShare = "${config.home.homeDirectory}/xdg-dirs/public";
    templates = "${config.home.homeDirectory}/xdg-dirs/templates";
  };

  home.packages = with pkgs; [ ];

  # Home Manager is pretty good at managing dotfiles. The primary way to manage
  # plain files is through 'home.file'.
  home.file = {
    # Building this configuration will create a copy of 'dotfiles/screenrc' in
    # the Nix store. Activating the configuration will then make '~/.screenrc' a
    # symlink to the Nix store copy.
    # ".screenrc".source = dotfiles/screenrc;
  };

  # Home Manager can also manage your environment variables through
  # 'home.sessionVariables'. If you don't want to manage your shell through Home
  # Manager then you have to manually source 'hm-session-vars.sh' located at
  #
  #  ~/.nix-profile/etc/profile.d/hm-session-vars.sh
  home.sessionVariables = {
    # EDITOR = "emacs";
  };

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;

  # This value determines the Home Manager release that your configuration is
  # compatible with. This helps avoid breakage when a new Home Manager release
  # introduces backwards incompatible changes.
  #
  # You should not change this value, even if you update Home Manager. If you do
  # want to update the value, then make sure to first check the Home Manager
  # release notes.
  home.stateVersion = "23.11"; # Please read the comment before changing.
}
