#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

source "$LIB_DIR/helpers-extra/apt-behaviour.sh"
source "$LIB_DIR/helpers/repo-helper.sh"

install_update_all_packages() {
  local base_dir="/usr/local/src"
  local repo_dir="$base_dir/update-all-the-packages"
  local install_script="$repo_dir/install-unattended-upgrades"

  _cmd "mkdir -p $base_dir"
  _cmd "chgrp docker $base_dir || true"
  _cmd "chmod g+w $base_dir"
  _cmd "chmod -s $base_dir"

  if [[ ! -d "$repo_dir" ]]; then
    info "Cloning update-all-the-packages repository"
    _cmd "git clone https://github.com/adamamyl/update-all-the-packages.git $repo_dir"
  else
    ok "$repo_dir already exists, skipping clone"
  fi

  if [[ ! -x "$install_script" ]]; then
    info "Making install-unattended-upgrades executable"
    _cmd "chmod +x $install_script"
  fi

  info "Running install-unattended-upgrades"
  _cmd "$install_script"
}
