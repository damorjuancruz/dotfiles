{ pkgs, ... }:

{
  boot = {
    kernelParams = ["quiet"];
    initrd.systemd.enable = true;
    plymouth = {
      enable = true;
      themePackages = with pkgs; [ nixos-bgrt-plymouth ];
      theme = "nixos-bgrt";
    };
  };
}
