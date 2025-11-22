#!/usr/bin/env bash
set -euo pipefail

install_tailscale() {
	if ! command -v tailscale >/dev/null 2>&1; then
		info "Installing Tailscale..."
		curl -fsSL https://tailscale.com/install.sh | sh
	else
		ok "Tailscale already installed"
	fi
}

ensure_tailscale_strict() {
	info "Enabling Tailscale SSH (Linux only)"
	if [[ "$(uname -s)" == "Linux" ]]; then
		tailscale set --ssh || warn "Failed to enable Tailscale SSH"
	fi
}
