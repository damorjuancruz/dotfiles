# Dotfiles

## Restore

```bash
paru -S aconfmgr
aconfmgr apply -c ~/dotfiles/system
stow home -d ~/dotfiles -t ~
sudo ~/.config/noctalia/plugins/battery-threshold/setup_rules.sh
systemctl --user enable --now ssh-agent
bun add -g btca
```
