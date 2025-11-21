#!/usr/bin/env bash
set -euo pipefail

install_docker_and_add_users() {
  if command -v docker >/dev/null 2>&1; then
    ok "Docker already installed, skipping"
  else
    info "Installing Docker"
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
  fi

  groupadd -f docker
  for user in adam no2id-docker; do
    if id "$user" >/dev/null 2>&1; then
      usermod -aG docker "$user"
    fi
  done
}
