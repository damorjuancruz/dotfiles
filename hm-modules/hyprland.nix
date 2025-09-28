{ config, pkgs, ... }:
{
  home.packages = with pkgs; [
    hyprpaper
  ];

  xdg.configFile.hypr.source = ./sources/hypr;
}
