#!/usr/bin/env bash
set -euo pipefail

install_gnome_tweaks() {
  if command -v gnome-tweaks >/dev/null 2>&1; then
    ok "gnome-tweaks already installed, skipping"
    return
  fi
  info "Installing gnome-tweaks"
  apt install -y gnome-tweaks
}
