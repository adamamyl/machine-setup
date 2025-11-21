#!/usr/bin/env bash
set -euo pipefail
HWGA_DIR="/usr/local/src"
NO2ID_REPO="git@github.com:no2id/herewegoagain.git"
FAKE_LE_REPO="git@github.com:adamamyl/fake-le.git"

setup_hwga_no2id() {
	require_user no2id-docker
	add_user_to_group no2id-docker docker

	local ssh_key="/root/.ssh/no2id-docker"
	if [[ ! -f "$ssh_key" ]]; then
		ssh-keygen -t ed25519 -f "$ssh_key" -N "" -C "no2id-docker@$(hostname)"
	fi

	info "Add the public key to: https://github.com/no2id/herewegoagain/settings/keys"
	cat "$ssh_key.pub"
	read -p "Press Enter once key is added..."

	local dest_dir="$HWGA_DIR/herewegoagain"
	clone_or_update_repo "$NO2ID_REPO" "$dest_dir" "$ssh_key"

	local fake_dir="$HWGA_DIR/fake-le"
	clone_or_update_repo "$FAKE_LE_REPO" "$fake_dir" "$ssh_key"
	if [[ -x "$fake_dir/fake-le-for-no2id-docker-installer" ]]; then
		"$fake_dir/fake-le-for-no2id-docker-installer"
	else
		warn "Fake-LE installer not executable"
	fi
	ok "HWGA / no2id setup complete"
}
