{ pkgs, ... }:
{
  home.file.".config/waybar/style.css".source = ./sources/waybar/style.css;
  home.file.".config/waybar/power_menu.xml".source = ./sources/waybar/power_menu.xml;
  programs.waybar={
    enable = true;
    settings.main = {
      # "layer" = "top"; # Waybar at top layer
      # "position" = "bottom"; # Waybar position (top|bottom|left|right)
      height = 30; # Waybar height (to be removed for auto height)
      # "width" = 1280; # Waybar width
      spacing = 4; # Gaps between modules (4px)

      # Choose the order of the modules
      modules-left = [
        "hyprland/workspaces"
        "hyprland/submap"
        # "custom/media"
      ];

      modules-center = [
        "clock"
      ];

      modules-right = [
        "pulseaudio"
        "backlight"
        "battery"
        "tray"
        "custom/power"
      ];

      "hyprland/workspaces" = {
        persistent-workspaces = {
          "*" = [ 1 2 3 4 5 ];
        };
        move-to-monitor = true;
        format = "{icon}";
        format-icons = {
          active = "";
          default = "";
          empty = "";
        };
      };

      tray = {
        # icon-size = 21;
        spacing = 10;
        # icons = {
        #   blueman = "bluetooth";
        #   TelegramDesktop = "$HOME/.local/share/icons/hicolor/16x16/apps/telegram.png";
        # };
      };

      clock = {
        timezone = "America/Argentina/Buenos_Aires";
        tooltip-format = "<big>{:%Y %B}</big>\n<tt><small>{calendar}</small></tt>";
        format-alt = "{:%Y-%m-%d}";
      };

      backlight = {
        # device = "acpi_video1";
        format = "{percent}% {icon}";
        format-icons = [ "" "" "" "" "" "" "" "" "" ];
      };

      battery = {
        states = {
          # good = 95;
          warning = 30;
          critical = 15;
        };
        format = "{capacity}% {icon}";
        format-full = "{capacity}% {icon}";
        format-charging = "{capacity}% ";
        format-plugged = "{capacity}% ";
        format-alt = "{time} {icon}";
        # format-good = ""; # An empty format will hide the module
        # format-full = "";
        format-icons = [ "" "" "" "" "" ];
      };

      pulseaudio = {
        # scroll-step = 1; # %, can be a float
        format = "{volume}% {icon} {format_source}";
        format-bluetooth = "{volume}% {icon} {format_source}";
        format-bluetooth-muted = " {icon} {format_source}";
        format-muted = " {format_source}";
        format-source = "{volume}% ";
        format-source-muted = "";
        format-icons = {
          headphone = "";
          hands-free = "";
          headset = "";
          phone = "";
          portable = "";
          car = "";
          default = [ "" "" "" ];
        };
        on-click = "pavucontrol";
      };

      # "custom/media" = {
      #   format = "{icon} {text}";
      #   return-type = "json";
      #   max-length = 40;
      #   format-icons = {
      #     spotify = "";
      #     default = "🎜";
      #   };
      #   escape = true;
      #   exec = "$HOME/.config/waybar/mediaplayer.py 2> /dev/null"; # Script in resources folder
      #   # exec = "$HOME/.config/waybar/mediaplayer.py --player spotify 2> /dev/null"; # Filter player based on name
      # };

      "custom/power" = {
        format = "⏻ ";
        tooltip = false;
        menu = "on-click";
        menu-file = "$HOME/.config/waybar/power_menu.xml"; # Menu file in resources folder
        menu-actions = {
          shutdown = "shutdown";
          reboot = "reboot";
          suspend = "systemctl suspend";
          hibernate = "systemctl hibernate";
        };
      };
    };
  };
}

