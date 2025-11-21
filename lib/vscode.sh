#!/usr/bin/env bash
set -euo pipefail
install_vscode(){ 
    command -v code >/dev/null 2>&1 || snap install --classic code; 
}
