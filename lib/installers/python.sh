#!/usr/bin/env bash
set -euo pipefail

VENVDIR="/opt/setup-venv"

ensure_python_and_venv() {
  if [[ ! -d /opt ]]; then
    err "/opt does not exist. Please create it before running this script."
    exit 1
  fi

  if [[ ! -w /opt ]]; then
    err "/opt is not writable. Run as root or adjust permissions."
    exit 1
  fi

  # Install python3 if missing
  if ! command -v python3 >/dev/null 2>&1; then
    info "Installing Python 3 and pip"
    apt_install python3 python3-pip
  else
    ok "Python3 already installed"
  fi

  # Determine Python minor version for the venv package
  local py_ver
  py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  local venv_pkg="python${py_ver}-venv"

  # Install corresponding python3.X-venv if not present
  if ! dpkg -s "$venv_pkg" >/dev/null 2>&1; then
    info "Installing $venv_pkg for venv support"
    apt_install "$venv_pkg"
  else
    ok "$venv_pkg already installed"
  fi

  # Create virtual environment if missing
  if [[ ! -d "$VENVDIR" ]]; then
    info "Creating Python virtual environment at $VENVDIR"
    python3 -m venv "$VENVDIR"
    "$VENVDIR/bin/pip" install --upgrade pip

    # Install dependencies if requirements.txt exists
    if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
      info "Installing Python dependencies from requirements.txt"
      "$VENVDIR/bin/pip" install -r "$REPO_ROOT/requirements.txt"
    fi
  else
    if [[ ! -w "$VENVDIR" ]]; then
      err "Virtual environment exists at $VENVDIR but is not writable."
      exit 1
    fi
    ok "Python virtual environment already exists at $VENVDIR and is writable"
  fi
}
