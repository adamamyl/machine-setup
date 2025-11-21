#!/usr/bin/env bash
set -euo pipefail

install_cloud_init_repo() {
  local src="/usr/local/src/post-cloud-init"
  if [[ ! -d "$src" ]]; then
    info "Cloning post-cloud-init repo"
    git clone https://github.com/adamamyl/post-cloud-init "$src"
    cd "$src" && ./install
  else
    ok "post-cloud-init already installed, skipping"
  fi
}
