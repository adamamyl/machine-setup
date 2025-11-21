#!/usr/bin/env bash
set -euo pipefail
install_vscode() {
	if ! command -v code >/dev/null 2>&1; then
		info "Installing VSCode..."
		wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg
		add-apt-repository "deb [arch=amd64] https://packages.microsoft.com/repos/code stable main"
		apt update
		apt install -y code
	else
		ok "VSCode already installed"
	fi
}
