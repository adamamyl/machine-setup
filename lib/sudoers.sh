#!/usr/bin/env bash
set -euo pipefail
setup_sudoers_staff() {
	local file="${1:-/etc/sudoers.d/staff}"
	if [[ -f "$file" && "$FORCE" != true ]]; then
		ok "$file already exists, skipping"
		return
	fi
	echo "%staff ALL=(ALL:ALL) NOPASSWD: ALL" >"$file"
	chmod 440 "$file"
	ok "Sudoers file $file installed"
}
