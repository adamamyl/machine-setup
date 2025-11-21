#!/usr/bin/env bash
set -euo pipefail
install_docker_and_add_users(){
    apt remove -y docker.io docker-compose docker-compose-plugin containerd runc || true
    command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
    groupadd -f docker; add_user_to_group "adam" "docker"
}
