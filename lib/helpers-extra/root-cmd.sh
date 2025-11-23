#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------------------------
# _root_cmd: run a command with guaranteed root privileges
#
# - Obeys DRY_RUN=true
# - Obeys QUIET=true/false (same semantics as _cmd)
# - Always uses a shell (bash -c) so pipelines, redirects, &&, || work
# - Behaves exactly like _cmd, but elevated
#
# Examples:
#   _root_cmd "mkdir -p /usr/local/src"
#   _root_cmd "groupadd -f docker"
#   _root_cmd "usermod -aG docker no2id || true"
# ----------------------------------------------------------------------
_root_cmd() {
  # Dry run handling
  if [[ "${DRY_RUN:-false}" == "true" ]]; then
    if [[ "${QUIET:-false}" != "true" ]]; then
      echo "[DRY-RUN] (root) $cmd"
    fi
    return 0
  fi

  # Actually run the command
  if [[ "$(id -u)" -eq 0 ]]; then
     if [[ "${QUIET:-false}" != "true" ]]; then
      echo "Running as root: $*"
    fi
    # Use array to preserve arguments safely
    bash -c 'set -- "$@"; "$@"' _ "$@"
  else
    # Elevate
    if [[ "${QUIET:-false}" != "true" ]]; then
      echo "Running as root: $*"
    fi
    sudo bash -c 'set -- "$@"; "$@"' _ "$@"
  fi
}
