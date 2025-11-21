#!/usr/bin/env bash
set -euo pipefail

install_vscode(){
    info "Installing VSCode"
    snap install --classic code
}
