# Software / Dependencies

<details>
  <summary>List</summary>
  
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
  - ly (AUR)
  - rate-mirrors (AUR)
  - pacman-contrib
  - tldr
  - hyprland (AUR)
  - hyprpaper-git (AUR)
  - wofi
  - pipewire
  - polkit-kde-agent
  - qt5-wayland & qt6-wayland
  - xdg-desktop-portal-hyprland-git (AUR, -gtk implementation)
  - grim & slurp
  - wlr-randr (AUR)
  - wev (AUR)
  - eww-wayland (AUR)
  - webcord (AUR, install electron manually)
  - grimshot
  - wl-clipboard
  - xdg-user-dirs
  - bat-asus-battery-bin (AUR)
  - rofi-lbonn-wayland-git (AUR)
  - ttf-firacode-nerd
  - noto-fonts-emoji
</details>

<details>
  <summary>Command</summary>
  
  ```bash
  paru -S alacritty fish pfetch exa bat neovim visual-studio-code-bin firefox cronie trash-cli awesome-git picom-jonaburg-git brightnessctl pamixer xclip acpi docker docker-compose ly rate-mirrors pacman-contrib tldr hyprland hyprpaper-git wofi pipewire polkit-kde-agent qt5-wayland qt6-wayland xdg-desktop-portal-gtk xdg-desktop-portal-hyprland-git grim slurp wlr-randr wev eww-wayland grimshot wl-clipboard xdg-user-dirs bat-asus-battery-bin rofi-lbonn-wayland-git ttf-firacode-nerd noto-fonts-emoji
  ```
</details>
<br>

# Other Settings

## limit charging to 85%

```shell
sudo bat-asus-battery threshold 85
sudo bat-asus-battery persist
```

## /etc/ly/config.ini

```diff
- #blank_password = true
+ #blank_password = true
```

## Wrapped Hyprland Wayland session

```
[Desktop Entry]
Name=hyprland
Comment=An intelligent dynamic tiling Wayland compositor
Exec=/home/juan/.config/hypr/wrapped-hyprland
Type=Application
```

## ssh-agent

Enable ssh-agent (file located at `.config/systemd/user/ssh-agent.service`) by running

```
systemctl --user enable --now ssh-agent
```

## Crontab

```
@daily $(which trash-empty) 30
```

## /etc/pacman.conf

```diff
- # Color
+ # Color

- # ParallelDownloads = 5
+ ParallelDownloads = 10
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
