{ inputs, pkgs, ... }:

{
  programs.git = {
    enable = true;

    userEmail = "damorjuancruz@gmail.com";
    userName = "Juan Cruz D'Amor";

    aliases = {
      graph = "log --color --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset'";
    };

    extraConfig = {
      remote.origin.prone = true;
      push = {
        autoSetupRemote = true;
        followTags = true;
      };
      init.defaultBranch = "main";

      gpg.format = "ssh";
    };
    signing = {
      signByDefault = true;
      key = "~/.ssh/id_ed25519.pub";
    };
  };
}

