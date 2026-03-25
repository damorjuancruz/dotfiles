#!/usr/bin/env bash

source ~/dotfiles/system/00-helpers.sh

white_list=(
  'etc/pacman.conf'
  'etc/security/faillock.conf'
  'etc/pam.d/system-auth'
  'etc/systemd/system/polkit-agent-helper@.service.d/override.conf'
)
IgnorePathsExcept "/" "${white_list[@]}"

CopyFile /etc/pacman.conf
CopyFile /etc/security/faillock.conf
CopyFile /etc/pam.d/system-auth
CopyFile /etc/systemd/system/polkit-agent-helper@.service.d/override.conf
