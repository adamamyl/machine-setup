#!/usr/bin/env bash
set -euo pipefail
setup_pseudohome() {
	local user="adam"
	require_user "$user"
	add_user_to_group "$user" staff
	install_ssh_keys "$user" "https://github.com/adamamyl.keys"

	local repo_url="git@github.com:adamamyl/pseudoadam.git"
	local base_dir
	base_dir="$(eval echo "~$user")"
	local dest_dir="$base_dir/pseudohome"
	if [[ ! -d "$dest_dir" ]]; then
		clone_or_update_repo "$repo_url" "$dest_dir"
		if [[ -x "$dest_dir/pseudohome-symlinks" ]]; then
			info "Running pseudohome symlinks"
			"$dest_dir/pseudohome-symlinks"
		else
			warn "Symlink installer not executable"
		fi
	else
		ok "Pseudohome already exists, skipping clone and symlinks"
	fi
}
