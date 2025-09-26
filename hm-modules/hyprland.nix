{ config, pkgs, ... }:
{
  home.packages = with pkgs; [
    hyprpaper
  ];

  home.file.".config/hypr" = {
    source = ./sources/hypr;
    recursive = true;
  };
}
