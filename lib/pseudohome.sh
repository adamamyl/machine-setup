#!/usr/bin/env bash
set -euo pipefail

setup_pseudohome() {
  local user="adam"
  local home_dir="/home/$user"
  local repo_dir="$home_dir/pseudohome"
  local symlink_script="$repo_dir/pseudohome-symlinks"
  local marker_file="$home_dir/.pseudohome-symlinks-done"

  require_user "$user"
  install_ssh_keys "$user" "https://github.com/adamamyl.keys"

  if [[ ! -d "$repo_dir" ]]; then
    info "Cloning pseudohome repository"
    sudo -u "$user" git clone --recursive git@github.com:adamamyl/pseudoadam.git "$repo_dir"
  else
    ok "$repo_dir already exists, skipping clone"
  fi

  if [[ ! -f "$marker_file" ]]; then
    if [[ -f "$symlink_script" ]]; then
      info "Applying pseudohome symlinks"
      sudo -u "$user" bash "$symlink_script"
      touch "$marker_file"
      chown "$user:$user" "$marker_file"
    else
      warn "Symlink script $symlink_script not found, skipping"
    fi
  else
    ok "Symlinks already applied, skipping"
  fi
}
