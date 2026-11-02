# Dotfiles

## Restore

```bash
paru -S aconfmgr
aconfmgr apply -c ~/dotfiles/system
stow home -d ~/dotfiles -t ~
systemctl --user enable --now ssh-agent
systemctl --user enable --now podman.socket
bun add -g btca
fnm install --lts
npm i -g pnpm
npm i -g eas-cli
```

Open seahorse and set the password for the Login keyring to blank.
