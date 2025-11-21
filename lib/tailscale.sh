#!/usr/bin/env bash
set -euo pipefail

install_tailscale() {
  if command -v tailscale >/dev/null 2>&1; then
    ok "Tailscale already installed, skipping"
    return
  fi
  info "Installing Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
}

ensure_tailscale_strict() {
  tailscale set --ssh || warn "Failed to enable Tailscale SSH"
}
