#!/usr/bin/env bash
set -euo pipefail

ensure_python_and_venv() {
    info "Ensuring Python 3 and virtual environment"

    # Install python3 if missing
    if ! command -v python3 >/dev/null 2>&1; then
        info "Python3 not found, installing..."
        if command -v apt >/dev/null 2>&1; then
            apt update
            apt install -y python3 python3-venv python3-pip
        elif command -v brew >/dev/null 2>&1; then
            brew install python
        else
            err "No package manager found to install Python3"
            exit 1
        fi
    fi

    # Create a venv in $REPO_ROOT/.venv if not exists
    VENV_DIR="$REPO_ROOT/.venv"
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating virtual environment in $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi

    # Activate venv and install requirements
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
        info "Installing Python requirements..."
        pip install --upgrade pip
        pip install -r "$REPO_ROOT/requirements.txt"
    fi
}
