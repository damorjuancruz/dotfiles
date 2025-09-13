{ pkgs, config, ... }:
{
  home.packages = with pkgs; [
    ghostty
    nerd-fonts.jetbrains-mono
  ];

  xdg.configFile.ghostty.source = config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/ghostty";
}
