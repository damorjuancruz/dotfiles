#!/usr/bin/env bash

function IgnorePathsExcept() {
  # Ignore all paths in the given directory (first parameter)
  # that do not match the given whitelist (second parameter)

  local search_dir="${1%/}"

  shift
  local white_list=("$@")
  local find_args=()
  local ignore_path

  if [[ "$search_dir" != "" && ! -d "$search_dir" ]]; then
    FatalError "The path ${search_dir} must be an existing directory\n"
  fi

  for ignore_path in "${white_list[@]}"; do
    local base="$ignore_path"
    if [[ "$ignore_path" =~ ^/ ]]; then
      FatalError "The path ${ignore_path} in the whitelist is not relative to the directory ${search_dir}\n"
    fi
    # Add all base paths to the argument list as well, otherwise
    # -prune will prevent us from reaching the whitelisted files.
    while [ "$base" != '.' ]; do
      find_args+=(-path "$search_dir/$base" -o)
      base="$(dirname "$base")"
    done
  done

  # Find everything except the given whitelist and the directory
  # being searched from
  sudo find "$search_dir/" -not \( "${find_args[@]}" -path "$search_dir/" \) -prune |
    while read -r file; do
      if [[ -d "$file" ]]; then
        IgnorePath "$file/*"
      fi
      IgnorePath "$file"
    done
}
