#!/usr/bin/env bash
set -euo pipefail

install_vscode() {
  if command -v code >/dev/null 2>&1; then
    ok "VSCode already installed, skipping"
    return
  fi
  info "Installing VSCode"
  snap install --classic code
}
