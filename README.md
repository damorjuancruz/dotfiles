# Dotfiles

## Restore

```bash
paru -S aconfmgr
aconfmgr apply -c ~/dotfiles/system
stow home -d ~/dotfiles -t ~
sudo ~/.config/noctalia/plugins/battery-threshold/setup_rules.sh
```
