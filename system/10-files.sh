#!/usr/bin/env bash

source ~/dotfiles/system/00-helpers.sh

white_list=(
  'etc/pacman.conf'
  'etc/security/faillock.conf'
  'etc/pam.d/system-auth'
  'etc/pam.d/system-local-login'
  'etc/pam.d/sudo'
  'etc/systemd/system/polkit-agent-helper@.service.d/override.conf'
  'etc/sddm.conf.d/autologin.conf'
  'etc/systemd/logind.conf'
  'etc/udev/rules.d/60-libfprint-2-goodix-55a4.rules'
  'etc/subuid'
  'etc/subgid'
)
IgnorePathsExcept "/" "${white_list[@]}"

CopyFile /etc/security/faillock.conf
CopyFile /etc/pam.d/system-auth
CopyFile /etc/systemd/system/polkit-agent-helper@.service.d/override.conf
CopyFile /etc/sddm.conf.d/autologin.conf
CopyFile /etc/systemd/logind.conf
CopyFile /etc/pam.d/sudo
CopyFile /etc/pam.d/system-local-login
CopyFile /etc/subgid
CopyFile /etc/subuid
CopyFile /etc/udev/rules.d/60-libfprint-2-goodix-55a4.rules
CopyFile /etc/pacman.conf

SetFileProperty / mode 555
