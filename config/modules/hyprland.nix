{ config, pkgs, ... }:

{
  wayland.windowManager.hyprland = {
    enable = true;
    settings = {
      # monitor = [
      #   "eDP-1, 1920x1080, 0x0, 1"
      #   "HDMI-A-1, 2560x1080, 1920x0, 1"
      # ];
      workspace = "1, monitor:HDMI-A-1, default:true";
      exec-once = [ ];
      exec = [ ];
      windowrulev2 = [
        "workspace 2, class:(telegram)"
        "workspace 2, class:(discord)"
        "workspace 2, class:(vesktop)"
        "workspace 1, class:(chrome)"
        "opacity 1.0 override, title:(HBO|YouTube)"
        "nomaximizerequest,class:(neovide)"
        "stayfocused,class:(Thunar),floating:1"
        "stayfocused,class:(Google-chrome),floating:1"
      ];
      input = {
        kb_layout = "us";
        kb_variant = "altgr-intl";
        numlock_by_default = true;

        follow_mouse = 1;
        accel_profile = "flat";
        float_switch_override_focus = true;

        touchpad = {
          natural_scroll = true;
          tap-and-drag = true;
          drag_lock = true;
        };
      };
      general = {
        gaps_in = 4;
        gaps_out = 8;
        border_size = 0;
        "col.active_border" = "rgb(ffffff)";
        "col.inactive_border" = "rgba(000000ff)";

        layout = "master";
      };
      decoration = {
        rounding = 12;
        inactive_opacity = 0.80;
        "col.shadow_inactive" = "rgba(00000000)";
        shadow_range = 16;
        shadow_render_power = 4;
        "col.shadow" = "rgba(ffffffff)";
        blur = {
          size = 12;
          passes = 3;
          ignore_opacity = true;
        };
      };
      misc = {
        disable_splash_rendering = true;
        force_default_wallpaper = 0;
      };
      animations = {
        enabled = true;

        bezier = [
          "easeOutQuint, 0.22, 1, 0.36, 1"
          "linear, 0, 0, 1, 1"
        ];

        animation = [
          "windows, 1, 5, easeOutQuint, slide"
          "border, 1, 2, linear"
          "fade, 1, 2, linear"
          "workspaces, 1, 6, easeOutQuint, slide"
        ];
      };

      master = {
        new_is_master = false;
        mfact = 0.5;
      };

      gestures = {
        workspace_swipe = true;
        workspace_swipe_distance = 100;
      };

      "$mod" = "ALT";

      "$swaylockCommand" = "swaylock --screenshots --clock --indicator --indicator-radius 100 --indicator-thickness 7 --effect-scale 0.5 --effect-pixelate 10 --effect-blur 50x5 --effect-vignette 0.4:0.7 --ring-color bb00cc --key-hl-color 880033 --line-color 00000000 --inside-color 00000088 --separator-color 00000000";

      "$setVolume" = "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@";

      bind = [
        "$mod, RETURN, exec, alacritty"
        "$mod, C, killactive"
        "$mod CTRL SHIFT, Q, exit"
        "$mod, Q, exec, $swaylockCommand"
        "$mod CTRL, Q, exec, $swaylockCommand"
        "$mod CTRL, Q, exec, systemctl suspend"
        "$mod SHIFT, Q, exec, nwg-bar"
        "$mod, F, togglefloating"
        "$mod, M, fullscreen"
        "$mod, S, focusmonitor, +1"

        ", switch:on:Lid Switch, exec, $swaylockCommand"


        ", XF86AudioMute, exec, wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"

        # ", Print, exec, shader=$(hyprshade current) && hyprshade off && flameshot gui && hyprshade on "${shader}""
      ];
      bindl = ", switch:on:Lid Switch, exec, systemctl suspend";
      binde = [
        ", XF86AudioRaiseVolume, exec, $setVolume 5%+"
        ", XF86AudioLowerVolume, exec, $setVolume 5%-"

        ", XF86MonBrightnessUp, exec, brightnessctl set 5%+"
        ", XF86MonBrightnessDown, exec, brightnessctl set 5%-"
      ];

    };
  };
}    

