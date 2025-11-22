#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

setup_pseudohome() {
  local user="adam"
  require_user "$user"
  add_user_to_group "$user" staff

  # Ensure user's .ssh exists
  local ssh_dir
  ssh_dir="$(eval echo "~$user")/.ssh"
  _cmd "mkdir -p -m 700 $ssh_dir"
  _cmd "chown $user:$user $ssh_dir"

  install_ssh_keys "$user" "https://github.com/adamamyl.keys"

  # Clone pseudohome repo
  local repo_url="git@github.com:adamamyl/pseudoadam.git"
  local base_dir
  base_dir="$(eval echo "~$user")"
  local dest_dir="$base_dir/pseudohome"

  if [[ ! -d "$dest_dir" ]]; then
    clone_or_update_repo "$repo_url" "$dest_dir"
    _cmd "chown -R $user:$user $dest_dir"
    _cmd "chmod -R g+w $dest_dir"

    if [[ -x "$dest_dir/pseudohome-symlinks" ]]; then
      info "Running pseudohome symlinks..." "$QUIET"
      _cmd "$dest_dir/pseudohome-symlinks"
    else
      warn "Symlink installer not executable" "$QUIET"
    fi
  else
    ok "Pseudohome already exists, skipping clone and symlinks" "$QUIET"
  fi
}
