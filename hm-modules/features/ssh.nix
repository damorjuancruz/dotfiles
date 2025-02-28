{ inputs, pkgs, ... }:

{
  programs.ssh = {
    enable = true;
    addKeysToAgent = "1h";
    matchBlocks = {
      linode-vps.hostname = "45.79.197.68";
    };
  };
}

