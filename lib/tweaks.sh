#!/usr/bin/env bash
set -euo pipefail

install_gnome_tweaks(){
    if is_gnome_desktop; then
        info "Installing GNOME Tweaks"
        apt update
        apt install -y gnome-tweaks
    fi
}
