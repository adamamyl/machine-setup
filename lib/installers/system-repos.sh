#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Install system-level GitHub repos
# ----------------------------------------------------------------------
install_linux_repos() {
  local base_dir="/usr/local/src"
  _root_cmd "safe_mkdir -p $base_dir"
  _root_cmd "safe_chgrp safe_docker $base_dir || true"
  _root_cmd "safe_chmod g+w $base_dir"
  _root_cmd "safe_chmod -s $base_dir"

  # Repos and their installer scripts
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

    # Clone or update the repo
    clone_or_update_repo "$repo_url" "$dest_dir"

    # Fix permissions
    _root_cmd "safe_chown -R root:root $dest_dir"
    _root_cmd "safe_chmod -R g+w $dest_dir"
    _root_cmd "safe_chmod -s $dest_dir"

    # Full path to installer
    local install_path="$dest_dir/$installer"
    if [[ -f "$install_path" && -x "$install_path" ]]; then
      info "Running $installer for $repo_name..." "$QUIET"
      # Run inside the repo directory, return to previous dir
      _root_cmd "pushd '$dest_dir' >/dev/null && './$installer' && popd >/dev/null"
    else
      warn "Installer $install_path missing or not executable, skipping" "$QUIET"
    fi
  done
}
