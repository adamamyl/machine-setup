#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id() {
	local user="no2id-docker"
	local base_dir="/usr/local/src"
	local venv_dir="/opt/setup-venv"  # path to venv created by python.sh

	mkdir -p "$base_dir"
	chgrp docker "$base_dir"
	chmod g+ws "$base_dir"

	if ! id "$user" >/dev/null 2>&1; then
		useradd -m -s /bin/bash "$user"
	fi

	local sshdir="/home/$user/.ssh"
	mkdir -p "$sshdir"
	chmod 700 "$sshdir"
	chown "$user:$user" "$sshdir"

	groupadd -f docker
	usermod -aG docker "$user"

	declare -A REPOS_KEYS=(
		["no2id/herewegoagain"]="id_ed25519_hwga"
		["adamamyl/fake-le"]="id_ed25519_fakele"
	)

	for repo in "${!REPOS_KEYS[@]}"; do
		local keyname="${REPOS_KEYS[$repo]}"
		local priv="$sshdir/$keyname"
		local pub="$priv.pub"

		if [[ ! -f "$pub" ]]; then
			info "Generating SSH key for $repo"
			sudo -u "$user" ssh-keygen -t ed25519 -f "$priv" -N "" -C "$user@$repo"
		fi
		chmod 600 "$priv" "$pub"
		chown "$user:$user" "$priv" "$pub"

		# Always use the venv python
		"$venv_dir/bin/python3" "$REPO_ROOT/tools/github-deploy-key.py" \
			--repo "$repo" --user "$user" --key-path "$pub"
	done

	for repo in "${!REPOS_KEYS[@]}"; do
		local keyname="${REPOS_KEYS[$repo]}"
		local priv="$sshdir/$keyname"
		local dest_dir="$base_dir/$(basename $repo)"

		if [[ ! -d "$dest_dir" ]]; then
			info "Cloning $repo"
			sudo -u "$user" env GIT_SSH_COMMAND="ssh -i $priv -o IdentitiesOnly=yes" \
				git clone "git@github.com:$repo.git" "$dest_dir"
		else
			ok "$dest_dir exists, skipping clone"
		fi
	done

	local fakele_dir="$base_dir/fake-le"
	if [[ -d "$fakele_dir" ]]; then
		"$fakele_dir/fake-le-for-no2id-docker-installer"
	fi
}
