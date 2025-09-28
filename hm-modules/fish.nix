{ pkgs, config, ... }:
{
  home.packages = with pkgs; [
    fish
    starship
    eza
    trash-cli
    bat
    fastfetch
    zoxide
    fzf
  ];

  xdg.configFile.fish.source = config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/fish";
}
