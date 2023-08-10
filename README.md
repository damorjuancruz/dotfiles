> These dotfiles are managed using `chezmoi`

# Software / Dependencies

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
  - nvim
  - cronie
  - trash-cli
  - docker & docker-compose
  - rate-mirrors (AUR)
  - pacman-contrib
  - tldr
  - xdg-user-dirs
  - bat-asus-battery-bin (AUR)
  - ttf-firacode-nerd
  - noto-fonts-emoji
  - unzip
  - fd
  - fzf
</details>

<details>
  <summary>Command</summary>
  
  ```bash
  paru -S chezmoi google-chrome alacritty fish pfetch exa bat neovim cronie trash-cli docker docker-compose rate-mirrors pacman-contrib tldr xdg-user-dirs bat-asus-battery-bin ttf-firacode-nerd noto-fonts-emoji unzip fd fzf
  ```
</details>
<br>

# Other Settings

## limit charging to 85%

```shell
sudo bat-asus-battery threshold 85
sudo bat-asus-battery persist
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

