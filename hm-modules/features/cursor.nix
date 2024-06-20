{ pkgs, ... }:
{
  home.pointerCursor = {
    gtk.enable = true;
    x11.enable = true;
    name = "Qogir-dark Cursors";
    package = pkgs.qogir-icon-theme;
    size = 16;
  };
}
