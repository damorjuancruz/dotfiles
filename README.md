# Software I Use / Dependencies

- paru (AUR)
- alacritty
- fish
- pfetch (AUR)
- exa
- bat
- nvim
- vscode (AUR)
- firefox
- cronie
- trash-cli
- awesome-git (AUR)
- picom-jonaburg-git (AUR)
- brightnesctl
- pamixer
- xclip
- acpi
- docker & docker-compose
- sddm-git (AUR)
- rate-mirrors (AUR)
- pacman-contrib

- hyprland (AUR)
- wofi
- pipewire
- polkit-kde-agent
- qt5-wayland & qt6-wayland
- xdg-desktop-portal-hyprland-git (AUR, -gtk implementation)
- wlr-randr (AUR)
- eww-wayland (AUR)
- socat
- jq

# Other Settings

## ssh-agent

Enable ssh-agent (file located at `.config/systemd/user/ssh-agent.service`) by running

```
systemctl --user enable --now ssh-agent
```

## Crontab

```
@daily $(which trash-empty) 30
```

## /etc/X11/xorg.conf.d/10-monitor.conf

```
Section "Monitor"
  Identifier  "HDMI-1"
  Option      "Primary" "true"
EndSection

Section "Monitor"
  Identifier  "eDP-1"
  Option      "LeftOf" "HDMI-1"
EndSection
```

## /etc/X11/xorg.conf.d/50-mouse-acceleration.conf

```
Section "InputClass"
	Identifier "My Mouse"
	MatchIsPointer "yes"
	Option "AccelerationProfile" "-1"
	Option "AccelerationScheme" "none"
	Option "AccelSpeed" "-1"
EndSection
```

## /etc/pacman.conf

Uncomment `Color` and set `ParallelDownloads` to 10
