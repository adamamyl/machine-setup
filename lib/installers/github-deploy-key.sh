#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY_SCRIPT="$REPO_ROOT/lib/github-deploy-key.py"

# Use Python from the venv if it exists
PYTHON_BIN="${VENVDIR:-/opt/setup-venv}/bin/python3"

run_github_deploy_key() {
    if [[ ! -f "$PY_SCRIPT" ]]; then
        echo "❌ Missing GitHub deploy key script: $PY_SCRIPT"
        return 1
    fi

    if [[ $# -lt 2 ]]; then
        echo "Usage: run_github_deploy_key <repo> <key_path>"
        return 1
    fi

    local repo="$1"
    local key_path="$2"
    shift 2

    if [[ ! -x "$PYTHON_BIN" ]]; then
        echo "❌ Python executable not found in virtual environment: $PYTHON_BIN"
        return 1
    fi

    # Always run inside venv
    "$PYTHON_BIN" "$PY_SCRIPT" "$repo" "$key_path" "$@"
}
