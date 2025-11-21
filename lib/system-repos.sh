#!/usr/bin/env bash
set -euo pipefail

install_linux_repos() {
	local cloud_repo="/usr/local/src/post-cloud-init"
	if [[ ! -d "$cloud_repo" ]]; then
		clone_or_update_repo "https://github.com/adamamyl/post-cloud-init.git" "$cloud_repo"
	fi
	if [[ -x "$cloud_repo/install" ]]; then
		info "Running post-cloud-init installer"
		"$cloud_repo/install"
	else
		warn "Installer not executable"
	fi

	local allpkg_repo="/usr/local/src/update-all-the-packages"
	if [[ ! -d "$allpkg_repo" ]]; then
		clone_or_update_repo "https://github.com/adamamyl/update-all-the-packages.git" "$allpkg_repo"
	fi
	chmod +w "$allpkg_repo/install-unattended-upgrades" || true
	"$allpkg_repo/install-unattended-upgrades"
}
