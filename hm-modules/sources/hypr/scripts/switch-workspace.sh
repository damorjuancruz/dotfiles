#! /usr/bin/env bash
# Script to make hyprland workspaces behave like qtile workspaces
# https://codeberg.org/JustineSmithies/hyprland-dotfiles/src/branch/master/.config/eww/scripts/dispatch.sh

activemonitor=$(hyprctl monitors -j | jq '.[] | select(.focused == true).id')
passivemonitor=$(hyprctl monitors -j | jq '.[] | select(.focused == false).id')
activews=$(hyprctl monitors -j | jq '.[] | select(.focused == true).activeWorkspace.id')
passivews=$(hyprctl monitors -j | jq '.[] | select(.focused == false).activeWorkspace.id')

[[ $1 -eq $passivews ]] && [[ $passivemonitor -ne $activemonitor ]] && (hyprctl dispatch swapactiveworkspaces "$activemonitor $passivemonitor")
hyprctl dispatch moveworkspacetomonitor "$1 $activemonitor"
hyprctl dispatch focusmonitor "$activemonitor"
hyprctl dispatch workspace "$activews"
hyprctl dispatch workspace "$1"
