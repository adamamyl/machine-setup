#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

VENVDIR="${VENVDIR:-/opt/setup-venv}"

# Return path to python executable in venv
venv_python() {
  local py="$VENVDIR/bin/python3"
  if [[ ! -x "$py" ]]; then
    err "Python executable not found in virtualenv at $py"
    exit 1
  fi
  echo "$py"
}

# Run a Python script inside venv
run_in_venv() {
  local script="$1"; shift
  "$(_venv_python)" "$script" "$@"
}
