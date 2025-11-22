#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

install_linux_repos() {
  local base_dir="/usr/local/src"
  _cmd "mkdir -p $base_dir"
  _cmd "chgrp docker $base_dir || true"
  _cmd "chmod g+w $base_dir"
  _cmd "chmod -s $base_dir"

  declare -A repos=(
    ["post-cloud-init"]="install"
    ["update-all-the-packages"]="install-unattended-upgrades"
  )
  declare -A urls=(
    ["post-cloud-init"]="https://github.com/adamamyl/post-cloud-init.git"
    ["update-all-the-packages"]="https://github.com/adamamyl/update-all-the-packages.git"
  )

  for repo_name in "${!repos[@]}"; do
    local installer="${repos[$repo_name]}"
    local repo_url="${urls[$repo_name]}"
    local dest_dir="$base_dir/$repo_name"

    clone_or_update_repo "$repo_url" "$dest_dir"

    _cmd "chown -R root:root $dest_dir"
    _cmd "chmod -R g+w $dest_dir"
    _cmd "chmod -s $dest_dir"

    local install_path="$dest_dir/$installer"
    if [[ -f "$install_path" && -x "$install_path" ]]; then
      info "Running $installer for $repo_name..." "$QUIET"
      _cmd "$install_path"
    else
      warn "Installer $install_path missing or not executable, skipping" "$QUIET"
    fi
  done
}
