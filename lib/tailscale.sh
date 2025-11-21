#!/usr/bin/env bash
set -euo pipefail
install_tailscale(){ 
    command -v tailscale >/dev/null 2>&1 || curl -fsSL https://tailscale.com/install.sh | sh; 
    }

ensure_tailscale_strict(){
    local tries=0; until tailscale status >/dev/null 2>&1 || (( tries >= 30 )); do sleep 2; tries=$((tries+1)); info "Waiting for Tailscale ($tries)"; done
    }
