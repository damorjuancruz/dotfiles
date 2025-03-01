{ pkgs, ... }: {
  home.file.".config/nvim-new" = {
    source = ./sources/nvim-config;
    recursive = true;
  };
  
  home.file.".config/lazyvim" = {
    source = ./sources/lazyvim;
    recursive = true;
  };

  programs.java.enable = true;

  programs.neovim = {
    enable = true;
    extraPackages = with pkgs; [
      gcc
      python3
      cmake
      git
      ripgrep
      fd
      unzip
      lazygit

      lua-language-server
      stylua
      # clang-tools
      # clang
      # libclang
      # nodePackages."@prisma/language-server"
      # nodePackages."@tailwindcss/language-server"
      # nodePackages.typescript-language-server
      # nodePackages.vscode-css-languageserver-bin
      # texlab
      # vscode-langservers-extracted
    ];
  };
}
