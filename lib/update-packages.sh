#!/usr/bin/env bash
set -euo pipefail

install_update_all_packages() {
	local base_dir="/usr/local/src"
	local repo_dir="$base_dir/update-all-the-packages"
	local install_script="$repo_dir/install-unattended-upgrades"

	# Prepare base dir
	mkdir -p "$base_dir"
	chgrp docker "$base_dir" || true
	chmod g+w "$base_dir"   # writable by group
	chmod -s "$base_dir"    # remove sticky/setgid bits

	if [[ ! -d "$repo_dir" ]]; then
		info "Cloning update-all-the-packages repository"
		git clone https://github.com/adamamyl/update-all-the-packages.git "$repo_dir"
	else
		ok "$repo_dir already exists, skipping clone"
	fi

	if [[ ! -x "$install_script" ]]; then
		info "Making install-unattended-upgrades executable"
		chmod +x "$install_script"
	fi

	info "Running install-unattended-upgrades"
	"$install_script"
}
