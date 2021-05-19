#!/usr/bin/env bash
xrandr --output DVI-D-1 --left-of HDMI-0 &
xinput --set-prop 21 'libinput Accel Profile Enabled' 0, 1 &
picom --experimental-backends &
volumeicon &
nm-applet --indicator &
emacs --daemon &
