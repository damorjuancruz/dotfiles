> These dotfiles are managed using `chezmoi`

# Software & Dependencies

<details>
  <summary>List</summary>
  
  - paru (AUR)
  - chezmoi
  - google-chrome
  - alacritty
  - fish
  - pfetch (AUR)
  - exa
  - bat
  - neovim
  - neovide
  - cronie
  - trash-cli
  - docker & docker-compose
  - rate-mirrors (AUR)
  - pacman-contrib
  - tldr
  - xdg-user-dirs
  - bat-asus-battery-bin (AUR)
  - ttf-firacode-nerd
  - noto-fonts
  - noto-fonts-emoji
  - unzip
  - fd
  - fzf
  - tmux 
  - rate-mirrors
  - wl-clipboad
  - dunst
  - pipewire
  - wireplumber
  - pipewire-pulse
  - pipewire-jack
  - xdg-desktop-portal-hyprland
  - polkit-kde-agent
  - qt5-wayland
  - qt6-wayland
  - waybar-hyprland-git
  - ripgrep
  - rofi-lbonn-wayland-git
  - discord
  - thunar
  - gvfs
  - hyprpaper
  - jq
  - telegram-desktop
  - bluez
  - bluez-utils
  - brightnessctl
  - grimblast-git
  - wlogout
  - gparted
  - xhost
  - ntfs-3g
  - htop
  - swaylock-effects
  - sddm
  - zip
  - xwaylandvideobridge-cursor-mode-2-git
  - meson
  - gjs
  - typescript
  - socat
  - gnome-bluetooth-3.0
  - upower
  - networkmanager
  - gobject-introspection
  - aylurs-gtk-shell
  - catppuccin-gtk-theme-mocha
  - nwg-look
</details>

<br>

# Other Settings

## Bat theme
```sh
bat cache --build
```

## limit charging to 85%

```shell
sudo bat-asus-battery threshold 85
sudo bat-asus-battery persist
```

## Enable Services

Enable ssh-agent (file located at `.config/systemd/user/ssh-agent.service`) by running

```
systemctl --user enable --now ssh-agent
systemctl --user enable --now tmux
sudo systemctl enable --now cronie
sudo systemctl enable --now bluetooth
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

## /etc/security/faillock.conf
```diff
- # deny = 3
+ deny = 10
```

