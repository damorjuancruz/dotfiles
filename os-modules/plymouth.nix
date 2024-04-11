{ pkgs, ... }:

{
  boot = {
    kernelParams = ["quiet"];
    initrd.systemd.enable = true;
    plymouth = {
      enable = true;
      themePackages = with pkgs; [
        (adi1090x-plymouth-themes.override {
          selected_themes = ["loader_alt"];
        })
      ];
      theme = "loader_alt";
    };
  };
}
