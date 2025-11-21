#!/usr/bin/env bash
set -euo pipefail
install_root_ssh_keys(){
    mkdir -p /root/.ssh; chmod 700 /root/.ssh
    [[ -f /root/.ssh/authorized_keys && "$FORCE" != true ]] && warn "Root authorized_keys exists, skipping" || curl -fsSL https://github.com/adamamyl.keys -o /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
}
install_user_ssh_keys(){
    local user="$1"; local sshdir="/home/$user/.ssh"
    mkdir -p "$sshdir"; chmod 700 "$sshdir"
    [[ -f "$sshdir/authorized_keys" && "$FORCE" != true ]] && warn "$user authorized_keys exists, skipping" || curl -fsSL https://github.com/adamamyl.keys -o "$sshdir/authorized_keys"
    chmod 600 "$sshdir/authorized_keys"
}
