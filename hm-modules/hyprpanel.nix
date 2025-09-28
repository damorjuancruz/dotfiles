{ config, ... }:
{
  programs.hyprpanel.enable = true;
  xdg.configFile.hyprpanel.source = config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/hyprpanel";
}
