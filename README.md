# My software

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

# Display Manager

Install `lightdm` package and enable it by running
`sudo systemctl enable lightdm`

# System files

/etc/X11/xorg.conf.d/10-monitor.conf:

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

/etc/pacman.conf
Uncomment `Color` and set `ParallelDownloads` to 10
