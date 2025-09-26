{ config, pkgs, ... }:

{
  home.packages = with pkgs; [
    tmux
    fzf
    bat
    eza
    upower
    zoxide
    sesh
    fd
  ];
  xdg.configFile."tmux".source =
    config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/tmux";
  xdg.configFile."sesh".source =
    config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/sesh";
}
