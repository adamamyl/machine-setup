#!/usr/bin/env bash
set -euo pipefail
install_gnome_tweaks() {
	if command -v gnome-tweaks >/dev/null 2>&1; then
		ok "GNOME Tweaks already installed"
	elif [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
		info "Installing GNOME Tweaks..."
		apt install -y gnome-tweaks
	else
		warn "GNOME Tweaks not installed (not Ubuntu Desktop)"
	fi
}
