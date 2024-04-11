{ inputs, pkgs, ... }:

{
  programs.ssh = {
    enable = true;
    addKeysToAgent = "1h";
  };
}

