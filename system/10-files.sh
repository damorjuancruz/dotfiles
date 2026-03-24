#!/usr/bin/env bash

source ~/dotfiles/system/00-helpers.sh

white_list=(
  'etc/pacman.conf'
  'etc/security/faillock.conf'
  'etc/pam.d/system-auth'
)
IgnorePathsExcept "/" "${white_list[@]}"

CopyFile /etc/pacman.conf
CopyFile /etc/pam.d/system-auth
CopyFile /etc/security/faillock.conf
