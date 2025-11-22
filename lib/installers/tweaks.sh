#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

source "$LIB_DIR/helpers-extra/apt-behaviour.sh"
source "$LIB_DIR/platform.sh"

install_gnome_tweaks() {
  if command -v gnome-tweaks >/dev/null 2>&1; then
    ok "GNOME Tweaks already installed"
  elif [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
    info "Installing GNOME Tweaks..."
    apt_install gnome-tweaks
  else
    warn "GNOME Tweaks not installed (not Ubuntu Desktop)"
  fi
}
