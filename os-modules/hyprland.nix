{ ... }:

{
  services.xserver = {
    enable = true; # Might need this for Xwayland  
    displayManager.sddm.enable = true;
  };

  programs.hyprland.enable = true;

  environment.sessionVariables.NIXOS_OZONE_WL = "1"; # This variable fixes electron apps in wayland
}
