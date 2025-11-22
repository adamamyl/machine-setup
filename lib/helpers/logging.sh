#!/usr/bin/env bash
set -euo pipefail
log_info() { if [[ "${QUIET:-false}" != true ]]; then info "$*"; fi }
log_ok() { if [[ "${QUIET:-false}" != true ]]; then ok "$*"; fi }
log_warn() { if [[ "${QUIET:-false}" != true ]]; then warn "$*"; fi }
log_err() { err "$*"; }

# Ensure a file exists with content; write default if missing or empty
ensure_file_with_content() {
  local file="$1"
  local default_content="$2"

  if [[ -s "$file" && "$FORCE" != true ]]; then
    log_ok "$file exists and is non-empty"
  else
    log_info "Creating/fixing $file..."
    echo "$default_content" >"$file"
    log_ok "$file installed or corrected"
  fi
}