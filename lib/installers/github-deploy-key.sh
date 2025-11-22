#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Wrapper for GitHub deploy key Python script
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY_SCRIPT="$REPO_ROOT/lib/github-deploy-key.py"

# Source python helper
source "$REPO_ROOT/lib/helpers/python.sh"

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

  # Ensure venv python exists
  local py
  py="$(venv_python)"

  # Run Python script inside venv
  "$py" "$PY_SCRIPT" "$repo" "$key_path" "$@"
}
