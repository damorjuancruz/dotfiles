#!/usr/bin/env bash

source ~/dotfiles/system/00-helpers.sh

white_list=(
  'etc/pacman.conf'
)
IgnorePathsExcept "/" "${white_list[@]}"

CopyFile /etc/pacman.conf
