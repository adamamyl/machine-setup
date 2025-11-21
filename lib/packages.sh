#!/usr/bin/env bash
set -euo pipefail
install_packages(){
    local PKGS=(diceware findutils grep gzip hostname iputils-ping net-tools openssh-server vim python3 git curl mtr)
    for pkg in "${PKGS[@]}"; do
        if command -v apt >/dev/null 2>&1; then 
            dpkg -s "$pkg" >/dev/null 2>&1 || apt install -y "$pkg"; 
        fi
        command -v brew >/dev/null 2>&1 && brew list "$pkg" >/dev/null 2>&1 || brew install "$pkg"
    done
}
