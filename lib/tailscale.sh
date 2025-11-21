#!/usr/bin/env bash
set -euo pipefail

install_tailscale(){
    info "Installing Tailscale"
    curl -fsSL https://tailscale.com/install.sh | sh
}

ensure_tailscale_strict(){
    info "Verifying Tailscale connectivity"
    local tries=0
    until tailscale status >/dev/null 2>&1 || (( tries >= 30 )); do sleep 2; tries=$((tries+1)); info "Waiting for Tailscale... ($tries)"; done
}
