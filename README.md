> These dotfiles are managed using `chezmoi`

# Software & Dependencies

<details>
  <summary>List</summary>
  
  - [x] hyprland
  - [~] paru (AUR)
  - [x] chezmoi
  - [x] google-chrome
  - [x] alacritty
  - [x] fish
  - [x] pfetch (AUR)
  - [x] exa
  - [x] bat
  - [x] neovim
  - [x] neovide
  - [x] cronie
  - [x] trash-cli
  - [x] docker & docker-compose
  - [~] rate-mirrors (AUR)
  - [~] pacman-contrib
  - [x] tldr
  - [x] xdg-user-dirs
  - [ ] bat-asus-battery-bin (AUR)
  - [x] ttf-firacode-nerd
  - [x] noto-fonts
  - [x] noto-fonts-emoji
  - [x] unzip
  - [x] fd
  - [x] fzf
  - [x] tmux 
  - [x] wl-clipboad
  - [x] pipewire
  - [x] wireplumber
  - [x] pipewire-pulse
  - [x] pipewire-jack
  - [x] xdg-desktop-portal-hyprland
  - [x] polkit-kde-agent
  - [ ] qt5-wayland
  - [ ] qt6-wayland
  - [x] ripgrep
  - [x] fuzzel
  - [x] discord
  - [x] thunar
  - [x] gvfs
  - [x] hyprpaper
  - [x] jq
  - [x] telegram-desktop
  - [x] bluez
  - [x] bluez-utils
  - [x] brightnessctl
  - [ ] grimblast-git
  - [x] nwg-bar
  - [x] gparted
  - [ ] xhost
  - [x] ntfs-3g
  - [x] htop
  - [x] swaylock-effects
  - [x] sddm
  - [x] zip
  - [ ] xwaylandvideobridge-cursor-mode-2-git
  - [ ] meson
  - [ ] gjs
  - [ ] typescript
  - [ ] socat
  - [ ] gnome-bluetooth-3.0
  - [ ] upower
  - [ ] networkmanager
  - [ ] gobject-introspection
  - [ ] aylurs-gtk-shell
  - [x] catppuccin-gtk-theme-mocha
  - [x] nwg-look
  - [x] linux-zen
  - [x] linux-zen-headers
  - [x] hyprshade
  - [x] rclone
  - [x] syncthing
  - [ ] virt-manager
  - [ ] virt-bootstrap
</details>

<br>

# Other Settings

## Bat theme
```sh
bat cache --build
```

## limit charging to 85%
```sh
sudo bat-asus-battery threshold 85
sudo bat-asus-battery persist
```

## Enable Services
```sh
systemctl --user enable --now ssh-agent
systemctl --user enable --now tmux
sudo systemctl enable --now cronie
sudo systemctl enable --now bluetooth
hyprshade install && systemctl --user enable --now hyprshade.timer
systemctl --user enable --now syncthing
```

## Crontab

```
@daily $(which trash-empty) 30
* * * * * rclone bisync ~/documents/ drive: --drive-skip-gdocs --check-access --create-empty-src-dirs
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

