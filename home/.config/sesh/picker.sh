#!/usr/bin/env bash

set -euo pipefail

pick_only=false

case "${1:-}" in
-p | --pick-only)
  pick_only=true
  ;;
esac

cd ~/code && ls -d */ | xargs -I {} zoxide add {}

selection="$(
  sesh list --icons | fzf --tmux=center,80%,70% \
    --no-sort --ansi --border-label ' sesh ' --prompt '⚡  ' \
    --header '  ^a all ^t tmux ^g configs ^x zoxide ^d tmux kill ^f find' \
    --bind 'ctrl-a:change-prompt(⚡  )+reload(sesh list --icons)' \
    --bind 'ctrl-t:change-prompt(🪟  )+reload(sesh list -t --icons)' \
    --bind 'ctrl-g:change-prompt(⚙️  )+reload(sesh list -c --icons)' \
    --bind 'ctrl-x:change-prompt(📁  )+reload(sesh list -z --icons)' \
    --bind 'ctrl-f:change-prompt(🔎  )+reload(fd -H -d 2 -t d -E .Trash . ~)' \
    --bind 'ctrl-d:execute(tmux kill-session -t {2..})+change-prompt(⚡  )+reload(sesh list --icons)' \
    --preview-window 'right:55%' \
    --preview 'sesh preview {}'
)"

if [[ -n "$selection" ]]; then
  if $pick_only; then
    echo $selection
  else
    sesh connect "$selection"
  fi
fi
