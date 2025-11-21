#!/usr/bin/env bash
set -euo pipefail

setup_hwga_no2id() {
	local user="no2id-docker"
	local base_dir="/usr/local/src"
	local venv_dir="/opt/setup-venv"  # must be created first
	local repos=(
		"no2id/herewegoagain"
		"adamamyl/fake-le"
	)
	declare -A keys=(
		["no2id/herewegoagain"]="id_ed25519_hwga"
		["adamamyl/fake-le"]="id_ed25519_fakele"
	)

	# Prepare base dir
	mkdir -p "$base_dir"
	chgrp docker "$base_dir" || true
	chmod g+ws "$base_dir"

	# Create user if missing
	if ! id "$user" >/dev/null 2>&1; then
		useradd -m -s /bin/bash "$user"
	fi

	# Setup SSH dir
	local sshdir="/home/$user/.ssh"
	mkdir -p "$sshdir"
	chmod 700 "$sshdir"
	chown "$user:$user" "$sshdir"

	# Add user to docker group
	groupadd -f docker
	usermod -aG docker "$user"

	for repo in "${repos[@]}"; do
		local keyname="${keys[$repo]}"
		local priv="$sshdir/$keyname"
		local pub="$priv.pub"

		# Generate SSH key if missing
		if [[ ! -f "$pub" ]]; then
			info "Generating SSH key for $repo"
			sudo -u "$user" ssh-keygen -t ed25519 -f "$priv" -N "" -C "$user@$repo"
		fi
		chmod 600 "$priv" "$pub"
		chown "$user:$user" "$priv" "$pub"

		# Validate deploy key via Python venv
		"$venv_dir/bin/python3" "$REPO_ROOT/tools/github-deploy-key.py" \
			--repo "$repo" --user "$user" --key-path "$pub"

		local dest_dir="$base_dir/$(basename $repo)"

		# Clone / update repo
		if [[ -d "$dest_dir/.git" ]]; then
			# Check repo health
			if ! git -C "$dest_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
				warn "Repo $dest_dir appears corrupted. Please remove and reclone manually:"
				echo "  sudo rm -rf $dest_dir"
				continue
			fi

			info "Updating $repo..."
			if ! GIT_SSH_COMMAND="ssh -i $priv -o IdentitiesOnly=yes" git -C "$dest_dir" fetch --all --prune; then
				warn "Fetch failed. Repo may be corrupted. Consider removing and recloning:"
				echo "  sudo rm -rf $dest_dir"
				continue
			fi
			# Reset to remote branch
			local branch
			branch=$(git -C "$dest_dir" rev-parse --abbrev-ref HEAD)
			GIT_SSH_COMMAND="ssh -i $priv -o IdentitiesOnly=yes" git -C "$dest_dir" reset --hard "origin/$branch"
		else
			info "Cloning $repo..."
			GIT_SSH_COMMAND="ssh -i $priv -o IdentitiesOnly=yes" git clone "git@github.com:$repo.git" "$dest_dir"
		fi

	done
}
