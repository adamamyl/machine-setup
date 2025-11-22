#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Default flags if not already exported
DRY_RUN="${DRY_RUN:-false}"
QUIET="${QUIET:-false}"
VERBOSE="${VERBOSE:-false}"
DEBUG="${DEBUG:-false}"

# Command runner respecting dry-run
_cmd() {
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] $*" "$QUIET"
  else
    eval "$@"
  fi
}
