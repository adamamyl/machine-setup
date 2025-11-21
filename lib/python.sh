#!/usr/bin/env bash
set -euo pipefail
ensure_python_and_venv(){
    command -v python3 >/dev/null 2>&1 || { info "Installing Python3"; apt update && apt install -y python3 python3-venv python3-pip; }
    local VENV_DIR="$REPO_ROOT/.venv"
    [[ ! -d "$VENV_DIR" ]] && python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    [[ -f "$REPO_ROOT/requirements.txt" ]] && pip install --upgrade pip && pip install -r "$REPO_ROOT/requirements.txt"
}
