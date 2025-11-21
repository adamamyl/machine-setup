#!/usr/bin/env bash
set -euo pipefail

install_docker_and_add_users(){
    # Check if docker exists
    if command -v docker >/dev/null 2>&1; then
        # Check if installed from official repo
        local ver_info
        ver_info=$(docker --version 2>/dev/null)
        if [[ "$ver_info" =~ "Docker version" ]]; then
            ok "Docker already installed: $ver_info"
            add_user_to_group "adam" "docker"
            return
        fi
    fi

    info "Installing Docker from official repo..."

    # Remove old docker packages only if not already official
    local old_pkgs=(docker.io docker-compose docker-compose-plugin containerd runc podman-docker)
    for pkg in "${old_pkgs[@]}"; do
        dpkg -s "$pkg" >/dev/null 2>&1 && apt remove -y "$pkg"
    done

    # Install Docker using official script
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh

    # Ensure docker group exists and add adam
    groupadd -f docker
    add_user_to_group "adam" "docker"
    ok "Docker installation complete."
}
