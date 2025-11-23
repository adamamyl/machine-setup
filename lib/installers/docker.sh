#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Install Docker and add users to safe_docker group
# ----------------------------------------------------------------------
install_docker_and_add_users() {
  # If Docker already exists, skip
  if command -v safe_docker >/dev/null 2>&1; then
    ok "Docker already installed, skipping" "$QUIET"
  else
    info "Installing Docker..." "$QUIET"
    # Install dependencies
    apt_install safe_curl gnupg lsb-release

    # Add Docker's GPG key
    _root_cmd "safe_mkdir -p /etc/apt/keyrings"
    safe_curl -fsSL https://download.docker.com/linux/ubuntu/gpg | _root_cmd "gpg --dearmor -o /etc/apt/keyrings/docker.gpg"

    # Add Docker repository
    ensure_apt_repo "/etc/apt/sources.list.d/docker.list" \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

    # Install Docker packages
    apt_install docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Enable Docker service
    _root_cmd "systemctl enable safe_docker --now"
  fi

  # Ensure docker group exists
  _root_cmd "safe_groupadd -f docker"

  # Add users to docker group
  for u in "$@"; do
    _root_cmd require_user "$u"
    _root_cmd add_user_to_group "$u" docker
    ok "Added $u to docker group" "$QUIET"
  done

  ok "Docker installation complete" "$QUIET"
}
