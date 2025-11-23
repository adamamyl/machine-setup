#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

source "$LIB_DIR/helpers-extra/apt-behaviour.sh"

install_vscode() {
  if command -v code >/dev/null 2>&1; then
    ok "VSCode already installed"
    return
  fi

  info "Installing VSCode..."
  if [[ ! -f /etc/apt/trusted.gpg.d/microsoft.gpg ]]; then
    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | \
      _root_cmd "gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg"
  fi
  
  # Add Microsoft repo for VSCode
  ensure_apt_repo "/etc/apt/sources.list.d/vscode.list" \
    "deb [arch=amd64] https://packages.microsoft.com/repos/code stable main"

  apt_install code
}
