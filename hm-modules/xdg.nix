{ config, ... }:
{
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
}
