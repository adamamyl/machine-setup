#!/usr/bin/env bash
set -euo pipefail

install_packages(){
    info "Installing standard packages"
    if command -v apt >/dev/null 2>&1; then
        PKGS=(diceware findutils grep gzip hostname iputils-ping net-tools openssh-server vim python3 git curl mtr)
        apt update
        apt install -y "${PKGS[@]}"
    elif command -v brew >/dev/null 2>&1; then
        PKGS=(vim git curl mtr)
        for p in "${PKGS[@]}"; do brew install "$p"; done
    fi
}
