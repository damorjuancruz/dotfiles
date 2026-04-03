#!/usr/bin/env bash

set -euo pipefail

pick_only=false

case "${1:-}" in
-p | --pick-only)
  pick_only=true
  ;;
esac

existing="$(zoxide query -l 2>/dev/null)"

add_if_needed() {
  [[ -d "$1" ]] || return 0
  local dir
  dir="$(realpath -m "$1")"

  grep -Fxq "$dir" <<<"$existing" || zoxide add "$dir"
}

for dir in ~/code/*; do
  [[ -d "$dir" ]] && add_if_needed "$dir"
done
add_if_needed ~/dotfiles
add_if_needed ~/documents/notes

selection="$(
  sesh list --hide-duplicates --icons | fzf --tmux=center,80%,70% \
    --no-sort --ansi --border-label ' sesh ' --prompt '⚡  ' \
    --header '  ^a all ^t tmux ^x zoxide ^d tmux kill ^f find' \
    --bind 'ctrl-a:change-prompt(⚡  )+reload(sesh list --hide-duplicates --icons)' \
    --bind 'ctrl-t:change-prompt(🪟  )+reload(sesh list -t --icons)' \
    --bind 'ctrl-x:change-prompt(📁  )+reload(sesh list -z --icons)' \
    --bind 'ctrl-f:change-prompt(🔎  )+reload(fd -H -d 2 -t d -E .Trash . ~)' \
    --bind 'ctrl-d:execute(tmux kill-session -t {2..})+change-prompt(⚡  )+reload(sesh list --hide-duplicates --icons)' \
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
