#!/usr/bin/env bash
set -euo pipefail

declare -A REPOS=(
    ["post-cloud-init"]="https://github.com/adamamyl/post-cloud-init.git"
    ["update-all-the-packages"]="https://github.com/adamamyl/update-all-the-packages.git"
)

declare -A INSTALLERS=(
    ["post-cloud-init"]="install"
    ["update-all-the-packages"]="install-unattended-upgrades"
)

install_linux_repos() {
	local base_dir="/usr/local/src"

	# Prepare base dir
	mkdir -p "$base_dir"
	chgrp docker "$base_dir" || true
	chmod g+w "$base_dir"   # writable by group
	chmod -s "$base_dir"    # remove sticky/setgid bits

	for repo_name in "${!REPOS[@]}"; do
		local repo_url="${REPOS[$repo_name]}"
		local dest_dir="$base_dir/$repo_name"
		local installer="${INSTALLERS[$repo_name]:-}"

		if [[ ! -d "$dest_dir" ]]; then
			info "Cloning $repo_name"
			git clone "$repo_url" "$dest_dir"
		else
			ok "$dest_dir already exists, skipping clone"
		fi

		if [[ -n "$installer" ]]; then
			local install_path="$dest_dir/$installer"
			if [[ ! -x "$install_path" ]]; then
				info "Making $install_path executable"
				chmod +x "$install_path"
			fi
			info "Running $install_path"
			"$install_path"
		fi
	done
}
