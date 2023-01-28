#!/usr/bin/python

import subprocess
import sys
import json

monitors = subprocess.run('hyprctl monitors -j', shell = True, stdout = subprocess.PIPE) # get monitors list
monitors = json.loads(monitors.stdout) # parse json from stdout

if len(monitors) > 0: # if there are more than one monitor
  for m in monitors:
    if m['focused']:
      active_monitor = m
    if not m['focused']:
      inactive_monitor = m

  if len(sys.argv) > 1: # receive target workspace as argument
    target_workspace = int(sys.argv[1])
  else: # swap workspaces if no argument is passed
    target_workspace = inactive_monitor['activeWorkspace']['id']

  if inactive_monitor['activeWorkspace']['id'] == target_workspace: # if the target workspace is in the inactive monitor, swap workspaces
    subprocess.run(f'hyprctl dispatch swapactiveworkspaces {inactive_monitor["id"]} {active_monitor["id"]}', shell = True)
    exit(0)
  # else, bring the target workspace to the active monitor
  subprocess.run(f'hyprctl dispatch moveworkspacetomonitor {active_monitor["id"]} {target_workspace}', shell = True)
elif len(sys.argv) > 1: # if there's only one monitor switch to the targe workspace
  target_workspace = int(sys.argv[1])
else: # throw error if there's only one monitor and no target workspace was provided
  exit(1)

# focus the target workspace
subprocess.run(f'hyprctl dispatch workspace {target_workspace}', shell = True)