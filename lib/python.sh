#!/usr/bin/env bash
set -euo pipefail

# Path to virtual environment
VENVDIR="/opt/setup-venv"

ensure_python_and_venv() {
    # Ensure /opt exists and is writable
    if [[ ! -d "/opt" ]]; then
        err "/opt does not exist. Please create it before running this script."
        exit 1
    fi
    if [[ ! -w "/opt" ]]; then
        err "/opt is not writable. Run as root or adjust permissions."
        exit 1
    fi

    # Install Python3 and venv if missing
    if ! command -v python3 >/dev/null 2>&1; then
        info "Installing Python 3 and pip"
        apt update
        apt install -y python3 python3-venv python3-pip
    else
        ok "Python3 already installed"
    fi

    # Create virtual environment if missing
    if [[ ! -d "$VENVDIR" ]]; then
        info "Creating Python virtual environment at $VENVDIR"
        python3 -m venv "$VENVDIR"
        "$VENVDIR/bin/pip" install --upgrade pip
        if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
            info "Installing Python dependencies from requirements.txt"
            "$VENVDIR/bin/pip" install -r "$REPO_ROOT/requirements.txt"
        fi
    else
        # Check if writable
        if [[ ! -w "$VENVDIR" ]]; then
            err "Virtual environment exists at $VENVDIR but is not writable."
            exit 1
        fi
        ok "Python virtual environment already exists at $VENVDIR and is writable"
    fi
}
