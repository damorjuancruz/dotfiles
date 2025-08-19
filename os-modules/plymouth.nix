{ pkgs, ... }:

{
  boot = {
    kernelParams = ["quiet"];
    initrd.systemd.enable = true;
    plymouth = {
      enable = true;
      # extraConfig = ''
      #   [Daemon]
      #   ShowDelay=5
      # '';
    };
  };
}
