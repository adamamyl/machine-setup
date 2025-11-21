#!/usr/bin/env bash
set -euo pipefail

setup_pseudohome(){
    info "Setting up pseudohome for adam"
    create_user "adam"
    install_user_ssh_keys "adam"
    add_user_to_group "adam" "staff"
    sudo -u adam git clone --recursive adam@git.amyl.org.uk:/data/git/pseudoadam /home/adam/pseudohome
    sudo -u adam /home/adam/pseudohome/pseudohome-symlinks || warn "pseudohome-symlinks not found"
}
