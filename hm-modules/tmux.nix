{ config, pkgs, ... }:

{
  home.packages = with pkgs; [
    fzf
    bat
    eza
    upower
    zoxide
  ];
  xdg.configFile."tmux".source = config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/tmux";
}
