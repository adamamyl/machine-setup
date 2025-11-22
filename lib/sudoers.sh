#!/usr/bin/env bash
set -euo pipefail

setup_sudoers_staff() {
  local file="${1:-/etc/sudoers.d/staff}"
  local content="%staff ALL=(ALL:ALL) NOPASSWD: ALL"

  ensure_file_with_content "$file" "$content"
  _cmd "chmod 440 $file"
  log_ok "Permissions for $file set to 440"
}
