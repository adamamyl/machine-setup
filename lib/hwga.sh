#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id(){
    create_user "no2id-docker"
    local sshdir="/home/no2id-docker/.ssh"
    mkdir -p "$sshdir"
    chmod 700 "$sshdir"

    [[ ! -f "$sshdir/id_ed25519.pub" ]] && ssh-keygen -t ed25519 -f "$sshdir/id_ed25519" -N "" -C "no2id-docker@$(hostname)"

    add_user_to_group "no2id-docker" "docker"

    # Use Python deploy key script
    "$TOOLS_DIR/github-deploy-key.py" \
        --repo "no2id/herewegoagain" \
        --user "no2id-docker" \
        --key-path "$sshdir/id_ed25519.pub"

    [[ -d /usr/src/herewegoagain ]] || sudo -u no2id-docker git clone git@github.com:no2id/herewegoagain.git /usr/src/herewegoagain
    [[ -d /usr/src/fake-le ]] || git clone git@github.com:adamamyl/fake-le.git /usr/src/fake-le
    /usr/src/fake-le/fake-le-for-no2id-docker-installer
}
