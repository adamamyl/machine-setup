#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id(){
    info "Setting up NO2ID / HWGA user"
    create_user "no2id-docker"
    local sshdir="/home/no2id-docker/.ssh"
    mkdir -p "$sshdir"; chmod 700 "$sshdir"
    ssh-keygen -t ed25519 -f "$sshdir/id_ed25519" -N "" -C "no2id-docker@$(hostname)"
    add_user_to_group "no2id-docker" "docker"
    "$TOOLS_DIR/github-deploy-key.py" --repo "no2id/herewegoagain" --user "no2id-docker" --key-path "$sshdir/id_ed25519.pub"
    sudo -u no2id-docker git clone git@github.com:no2id/herewegoagain.git /usr/src/herewegoagain
    git clone git@github.com:adamamyl/fake-le.git /usr/src/fake-le
    /usr/src/fake-le/fake-le-for-no2id-docker-installer
}
