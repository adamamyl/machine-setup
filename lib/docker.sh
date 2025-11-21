#!/usr/bin/env bash
set -euo pipefail

install_docker_and_add_users(){
    info "Installing Docker"
    apt remove -y docker.io docker-compose docker-compose-plugin containerd runc || true
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    groupadd -f docker
    add_user_to_group "adam" "docker"
}
