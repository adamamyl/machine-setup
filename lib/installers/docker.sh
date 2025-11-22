#!/usr/bin/env bash
set -euo pipefail

source "$LIB_DIR/apt-behaviour.sh"

install_docker_and_add_users() {
  if command -v docker >/dev/null 2>&1; then
    info "Docker already installed, skipping" "$QUIET"
  else
    info "Installing Docker..." "$QUIET"
    apt_install curl
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
  fi
  groupadd -f docker
  usermod -aG docker adam || true
  ok "Docker installation complete and user groups updated" "$QUIET"
}
