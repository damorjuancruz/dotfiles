#!/usr/bin/python

import subprocess
import os
import socket
import json

def update_workspaces():
  # get monitors
  monitors = subprocess.run(f"hyprctl monitors -j", stdout=subprocess.PIPE, shell=True)
  # parse output
  monitors = json.loads(monitors.stdout)

  # get active workspaces
  active_workspace_primary = monitors[1]["activeWorkspace"]["id"]
  active_workspace_secondary = monitors[0]["activeWorkspace"]["id"]

  # get workspaces
  workspaces = subprocess.run(f"hyprctl workspaces -j", stdout=subprocess.PIPE, shell=True)
  # parse
  workspaces = json.loads(workspaces.stdout)

  result = []
  # generate widget
  for i in range(1, 6):
    w = {
      'id': i
    }

    # get amount of windows in workspace with id == i
    windows = 0
    for workspace in workspaces:
      if int(workspace["id"]) == i:
        windows = workspace["windows"]
        break
    
    # set "empty" class if there are no windows
    empty_class = "empty" if windows == 0 else ""
    # set focus-related class
    if i == active_workspace_primary:
      focus_class = "primary"
    elif i == active_workspace_secondary:
      focus_class = "secondary"
    else:
      focus_class = ""

    w['special_classes'] = f'{focus_class} {empty_class}'

    result.append(w)

  # output
  subprocess.run(f"echo '{json.dumps(result)}'", 
    shell=True)

# subscribe to hyprland socket 2
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server_address = f"/tmp/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
sock.connect(server_address)

update_workspaces() # initial render

while True:
  sock.recv(4096).decode("utf-8") # wait for socket message
  update_workspaces() # update workspaces widget on each message
