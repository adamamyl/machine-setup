#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id(){
    local user="no2id-docker"
    local base_dir="/usr/local/src"
    local docker_group="docker"

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

    # Ensure user is in docker group
    groupadd -f docker
    usermod -aG docker "$user"

    # Define private repos and deploy keys
    declare -A REPOS_KEYS=(
        ["no2id/herewegoagain"]="id_ed25519_hwga"
        ["adamamyl/fake-le"]="id_ed25519_fakele"
    )

    # Generate SSH keys for each repo
    for repo in "${!REPOS_KEYS[@]}"; do
        local keyname="${REPOS_KEYS[$repo]}"
        local priv="$sshdir/$keyname"
        local pub="$priv.pub"
        if [[ ! -f "$pub" ]]; then
            info "Generating SSH key for $repo"
            sudo -u "$user" ssh-keygen -t ed25519 -f "$priv" -N "" -C "$user@$repo"
        fi
        chmod 600 "$priv" "$pub"
        chown "$user:$user" "$priv" "$pub"

        # Interactive GitHub deploy key confirmation
        "$TOOLS_DIR/github-deploy-key.py" --repo "$repo" --user "$user" --key-path "$pub"
    done

    # Clone each repo using its dedicated deploy key
    for repo in "${!REPOS_KEYS[@]}"; do
        local keyname="${REPOS_KEYS[$repo]}"
        local priv="$sshdir/$keyname"
        local dest_dir="$base_dir/$(basename $repo)"

        if [[ ! -d "$dest_dir" ]]; then
            info "Cloning $repo"
            sudo -u "$user" env GIT_SSH_COMMAND="ssh -i $priv -o IdentitiesOnly=yes" \
                git clone "git@github.com:$repo.git" "$dest_dir"
        else
            ok "$dest_dir exists, skipping clone"
        fi
    done

    # Run fake-le installer (assumes cloned path)
    local fakele_dir="$base_dir/fake-le"
    if [[ -d "$fakele_dir" ]]; then
        "$fakele_dir/fake-le-for-no2id-docker-installer"
    fi
}
