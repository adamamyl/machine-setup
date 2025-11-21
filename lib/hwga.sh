#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id(){
    local user="no2id-docker"
    local sshdir="/home/$user/.ssh"
    local privkey="$sshdir/id_ed25519"
    local pubkey="$privkey.pub"
    local repo_dir="/usr/local/src/herewegoagain"
    local fake_le_dir="/usr/local/src/fake-le"
    local REPO="no2id/herewegoagain"

    # Ensure user exists
    if ! id "$user" >/dev/null 2>&1; then
        info "Creating user $user"
        useradd -m -s /bin/bash "$user"
    fi

    # Create SSH directory with proper permissions
    mkdir -p "$sshdir"
    chmod 700 "$sshdir"
    chown "$user:$user" "$sshdir"

    # Generate SSH key if missing
    if [[ ! -f "$pubkey" ]]; then
        info "Generating SSH key for $user"
        sudo -u "$user" ssh-keygen -t ed25519 -f "$privkey" -N "" -C "$user@$(hostname)"
    fi
    chmod 600 "$privkey" "$pubkey"
    chown "$user:$user" "$privkey" "$pubkey"

    # Ensure user is in docker group
    groupadd -f docker
    usermod -aG docker "$user"

    # Call Python deploy key script interactively
    "$TOOLS_DIR/github-deploy-key.py" \
        --repo "$REPO" \
        --user "$user" \
        --key-path "$pubkey"

    # Clone repositories if they do not exist
    if [[ ! -d "$repo_dir" ]]; then
        info "Cloning herewegoagain repo"
        sudo -u "$user" git clone "git@github.com:$REPO.git" "$repo_dir"
    else
        ok "$repo_dir already exists, skipping clone"
    fi

    if [[ ! -d "$fake_le_dir" ]]; then
        info "Cloning fake-le repo"
        git clone git@github.com:adamamyl/fake-le.git "$fake_le_dir"
    else
        ok "$fake_le_dir already exists, skipping clone"
    fi

    # Run fake-le installer
    "$fake_le_dir/fake-le-for-no2id-docker-installer"
}
