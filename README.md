# Software I Use / Dependencies

- cronie
- trash-cli
- exa
- bat
- alacritty
- firefox
- brightnesctl
- pamixer
- nvim
- xclip

## AUR

- paru
- pfetch
- awesome-git
- picom-jonaburg-git
- vscode

# Other Settings

## Crontab

```
@daily $(which trash-empty) 30
```

## /etc/X11/xorg.conf.d/10-monitor.conf:

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

## /etc/pacman.conf

Uncomment `Color` and set `ParallelDownloads` to 10
