#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id(){
    local user="no2id-docker"
    local base_dir="/usr/local/src"
    local docker_group="docker"
    local REPO_HWGA="no2id/herewegoagain"
    local REPO_FAKELE="adamamyl/fake-le"

    # Ensure base dir exists with proper group permissions
    mkdir -p "$base_dir"
    chgrp "$docker_group" "$base_dir"
    chmod g+ws "$base_dir"

    # Ensure user exists
    if ! id "$user" >/dev/null 2>&1; then
        info "Creating user $user"
        useradd -m -s /bin/bash "$user"
    fi

    # Create SSH dir
    local sshdir="/home/$user/.ssh"
    mkdir -p "$sshdir"
    chmod 700 "$sshdir"
    chown "$user:$user" "$sshdir"

    # --- Deploy key for herewegoagain ---
    local hwga_priv="$sshdir/id_ed25519_hwga"
    local hwga_pub="$hwga_priv.pub"
    if [[ ! -f "$hwga_pub" ]]; then
        info "Generating deploy key for $REPO_HWGA"
        sudo -u "$user" ssh-keygen -t ed25519 -f "$hwga_priv" -N "" -C "$user@$REPO_HWGA"
    fi
    chmod 600 "$hwga_priv" "$hwga_pub"
    chown "$user:$user" "$hwga_priv" "$hwga_pub"

    # --- Deploy key for fake-le ---
    local fakele_priv="$sshdir/id_ed25519_fakele"
    local fakele_pub="$fakele_priv.pub"
    if [[ ! -f "$fakele_pub" ]]; then
        info "Generating deploy key for $REPO_FAKELE"
        sudo -u "$user" ssh-keygen -t ed25519 -f "$fakele_priv" -N "" -C "$user@$REPO_FAKELE"
    fi
    chmod 600 "$fakele_priv" "$fakele_pub"
    chown "$user:$user" "$fakele_priv" "$fakele_pub"

    # Ensure user in docker group
    groupadd -f docker
    usermod -aG docker "$user"

    # --- Interactive deploy key confirmation ---
    "$TOOLS_DIR/github-deploy-key.py" --repo "$REPO_HWGA" --user "$user" --key-path "$hwga_pub"
    "$TOOLS_DIR/github-deploy-key.py" --repo "$REPO_FAKELE" --user "$user" --key-path "$fakele_pub"

    # --- Clone repos if missing ---
    local hwga_dir="$base_dir/herewegoagain"
    local fakele_dir="$base_dir/fake-le"

    if [[ ! -d "$hwga_dir" ]]; then
        info "Cloning $REPO_HWGA"
        sudo -u "$user" git clone "git@github.com:$REPO_HWGA.git" "$hwga_dir"
    else
        ok "$hwga_dir exists, skipping clone"
    fi

    if [[ ! -d "$fakele_dir" ]]; then
        info "Cloning $REPO_FAKELE"
        sudo -u "$user" git clone "git@github.com:$REPO_FAKELE.git" "$fakele_dir"
    else
        ok "$fakele_dir exists, skipping clone"
    fi

    # Run fake-le installer
    "$fakele_dir/fake-le-for-no2id-docker-installer"
}
