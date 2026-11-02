#!/usr/bin/env bash

source ~/dotfiles/system/00-helpers.sh

white_list=(
  'etc/pacman.conf'
  'etc/security/faillock.conf'
  'etc/pam.d/system-auth'
  'etc/systemd/system/polkit-agent-helper@.service.d/override.conf'
  'etc/sddm.conf.d/autologin.conf'
  'etc/subuid'
  'etc/subgid'
  'etc/containers/nodocker'
  'etc/pam.d/sudo'
  'etc/pam.d/system-local-login'
  'etc/systemd/logind.conf'
  'etc/udev/rules.d/60-libfprint-2-goodix-55a4.rules'
)
IgnorePathsExcept "/" "${white_list[@]}"

CopyFile /etc/pacman.conf
CopyFile /etc/security/faillock.conf
CopyFile /etc/pam.d/system-auth
CopyFile /etc/systemd/system/polkit-agent-helper@.service.d/override.conf
CopyFile /etc/sddm.conf.d/autologin.conf
CopyFile /etc/subgid
CopyFile /etc/subuid
CreateFile /etc/containers/nodocker > /dev/null
CopyFile /etc/pam.d/sudo
CopyFile /etc/pam.d/system-local-login
CopyFile /etc/systemd/logind.conf
CopyFile /etc/udev/rules.d/60-libfprint-2-goodix-55a4.rules

SetFileProperty / mode 555
