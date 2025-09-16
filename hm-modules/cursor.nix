{ pkgs, ... }:
{
  home.pointerCursor = {
    gtk.enable = true;
    x11.enable = true;
    name = "capitaine-cursors-white";
    package = pkgs.capitaine-cursors;
    size = 32;
  };
}
