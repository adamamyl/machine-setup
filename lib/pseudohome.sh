#!/usr/bin/env bash
set -euo pipefail
setup_pseudohome(){
    create_user "adam"
    install_user_ssh_keys "adam"
    add_user_to_group "adam" "staff"
    local dest="/home/adam/pseudohome"
    if [[ -d "$dest" && -n "$(ls -A "$dest")" ]]; then warn "$dest exists, skipping clone"; else sudo -u adam git clone --recursive adam@git.amyl.org.uk:/data/git/pseudoadam "$dest"; fi
    [[ -x "$dest/pseudohome-symlinks" ]] && sudo -u adam "$dest/pseudohome-symlinks" || warn "pseudohome-symlinks not found"
}
