#!/usr/bin/env bash
set -euo pipefail
install_gnome_tweaks(){ 
    is_gnome_desktop && command -v gnome-tweaks >/dev/null 2>&1 || apt install -y gnome-tweaks; 
}
