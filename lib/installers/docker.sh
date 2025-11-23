#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Install Docker and add users to docker group
# ----------------------------------------------------------------------
install_docker_and_add_users() {
  # If Docker already exists, skip
  if command -v docker >/dev/null 2>&1; then
    ok "Docker already installed, skipping" "$QUIET"
  else
    info "Installing Docker..." "$QUIET"
    # Install dependencies
    apt_install curl gnupg lsb-release

    # Add Docker's GPG key
    _cmd "mkdir -p /etc/apt/keyrings"
    _cmd "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg"

    # Add Docker repository
    _cmd 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list'

    # Install Docker packages
    apt_install docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Enable Docker service
    _cmd "systemctl enable docker --now"
  fi

  # Ensure docker group exists
  groupadd -f docker

  # Add users to docker group
  for u in "$@"; do
    require_user "$u"
    add_user_to_group "$u" docker
    ok "Added $u to docker group" "$QUIET"
  done

  ok "Docker installation complete" "$QUIET"
}
