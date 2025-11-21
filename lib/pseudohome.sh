#!/usr/bin/env bash
set -euo pipefail

setup_pseudohome() {
  local user="adam"
  local home_dir="/home/$user"
  local repo_dir="$home_dir/pseudohome"
  local symlink_script="$repo_dir/pseudohome-symlinks"
  local marker_file="$home_dir/.pseudohome-symlinks-done"

  # Ensure user exists
  if ! id "$user" >/dev/null 2>&1; then
    info "Creating user $user"
    useradd -m -s /bin/bash "$user"
  fi

  # Install SSH keys
  install_ssh_keys "$user" "https://github.com/adamamyl.keys"

  # Clone pseudohome repo if missing
  if [[ ! -d "$repo_dir" ]]; then
    info "Cloning pseudohome repo"
    sudo -u "$user" git clone --recursive git@github.com:adamamyl/pseudoadam.git "$repo_dir"
  else
    ok "$repo_dir already exists, skipping clone"
  fi

  # Run symlinks script only once
  if [[ ! -f "$marker_file" ]]; then
    if [[ -f "$symlink_script" ]]; then
      info "Applying symlinks for $user"
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
