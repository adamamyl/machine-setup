#!/usr/bin/env bash
set -euo pipefail

install_packages() {
  info "Installing standard packages"
  local pkgs=(diceware findutils grep gzip hostname iputils-ping net-tools openssh-server vim python3 git curl mtr)
  apt update
  for pkg in "${pkgs[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      apt install -y "$pkg"
    else
      ok "$pkg already installed, skipping"
    fi
  done
}
