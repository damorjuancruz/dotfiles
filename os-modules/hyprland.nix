{ pkgs, config, ... }:

{
  services.xserver.enable = true; # Might need this for Xwayland  
  services.greetd = {
    enable = true;
    settings = {
      default_session = {
        command = "${config.programs.hyprland.package}/bin/Hyprland --config /etc/greetd/hyprland.conf";
      };
      initial_session = {
        command = "${config.programs.hyprland.package}/bin/Hyprland";
        user = "jcdamor";
      };
    };
  };
  programs.regreet = {
    enable = true;
  };

  environment.etc."greetd/hyprland.conf".text = ''
    exec-once = ${config.programs.regreet.package}/bin/regreet; ${config.programs.hyprland.package}/bin/hyprctl dispatch exit
    misc {
        disable_hyprland_logo = true
        disable_splash_rendering = true
        disable_hyprland_qtutils_check = true # Hyprland v0.46+
    }
  '';

  programs.hyprland = {
    enable = true;
    # package = pkgs.unstable.hyprland;
    # portalPackage = pkgs.unstable.xdg-desktop-portal-hyprland;
  };

  environment.sessionVariables.NIXOS_OZONE_WL = "1"; # This variable fixes electron apps in wayland
}
