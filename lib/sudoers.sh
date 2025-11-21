#!/usr/bin/env bash
set -euo pipefail

setup_sudoers_staff() {
  local file_path="${1:-/etc/sudoers.d/staff}"
  local content="%staff  ALL=(ALL:ALL) NOPASSWD: ALL"

  if [[ -f "$file_path" ]]; then
    ok "$file_path already exists, skipping"
    return
  fi

  info "Creating sudoers file at $file_path"
  echo "$content" > "$file_path"
  chmod 440 "$file_path"
  chown root:root "$file_path"
}
