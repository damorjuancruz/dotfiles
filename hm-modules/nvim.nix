{ config, pkgs, ... }:
let
  lspPkgs = with pkgs; [
    lua-language-server
  ];

  buildTools = with pkgs; [
    gcc
    gnumake
    pkg-config
    python3
    cmake
  ];

  tools = with pkgs; [
    git
    ripgrep
    ast-grep
    fd
    lazygit
    wl-clipboard
  ];

  neovim-with-env = pkgs.symlinkJoin {
    name = "neovim";
    meta = pkgs.neovim-unwrapped.meta;
    lua = pkgs.neovim-unwrapped.lua;
    paths = [ pkgs.neovim-unwrapped ];
    buildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram $out/bin/nvim \
        --set NVIM_IS_NIXOS "1" \
    '';
  };
in
{
  programs.neovim = {
    enable = true;

    package = neovim-with-env;

    # defaultEditor = true;
    # viAlias = true;
    # vimAlias = true;

    withNodeJs = true;
    withPython3 = true;

    extraPackages = lspPkgs ++ buildTools ++ tools;
  };

  xdg.configFile.lazyvim.source = config.lib.file.mkOutOfStoreSymlink "${config.dotfiles-path}/hm-modules/sources/nvim";
  xdg.configFile."lazygit/config.yml".text = "";
}
