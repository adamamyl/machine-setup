#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

HWGA_DIR="/usr/local/src"

# Array of repos with their users and optional installer scripts
declare -A HWGA_REPOS=(
  ["herewegoagain"]="no2id-docker:/usr/local/src/herewegoagain:install"
  ["fake-le"]="adam:/usr/local/src/fake-le:fake-le-for-no2id-docker-installer"
)

NO2ID_REPO="git@github.com:no2id/herewegoagain.git"
FAKE_LE_REPO="git@github.com:adamamyl/fake-le.git"

setup_hwga_no2id() {
  info "Starting HWGA / no2id setup..." "$QUIET"

  # Ensure group exists and base dir is writable
  groupadd -f docker
  _cmd "mkdir -p $HWGA_DIR"
  _cmd "chgrp docker $HWGA_DIR"
  _cmd "chmod g+w $HWGA_DIR"
  _cmd "chmod -s $HWGA_DIR"

  # Loop through repos
  for repo_name in "${!HWGA_REPOS[@]}"; do
    IFS=':' read -r user dest_dir installer <<< "${HWGA_REPOS[$repo_name]}"
    local ssh_dir
    ssh_dir="$(eval echo "~$user")/.ssh"

    require_user "$user"
    add_user_to_group "$user" docker

    # Ensure user's .ssh exists
    _cmd "mkdir -p -m 700 $ssh_dir"
    _cmd "chown $user:$user $ssh_dir"

    # Generate deploy key if missing
    if [[ ! -f "$ssh_dir/$repo_name" ]]; then
      info "Generating SSH key for $repo_name..." "$QUIET"
      _cmd "ssh-keygen -t ed25519 -f $ssh_dir/$repo_name -N '' -C '${user}@$(hostname)'"
    fi
    _cmd "chmod 600 $ssh_dir/$repo_name"
    _cmd "chown $user:$user $ssh_dir/$repo_name"

    # Prompt user to add public key if first time
    info "Ensure this public key is added to GitHub for repo $repo_name:"
    cat "$ssh_dir/$repo_name.pub"
    read -p "Press Enter once added..."

    # Determine repo URL
    local repo_url
    if [[ "$repo_name" == "herewegoagain" ]]; then
      repo_url="$NO2ID_REPO"
    else
      repo_url="$FAKE_LE_REPO"
    fi

    # Run Python deploy key script using venv
    run_github_deploy_key "$repo_url" "$ssh_dir/$repo_name"

    # Clone or update repo using correct deploy key
    clone_or_update_repo "$repo_url" "$dest_dir" "$ssh_dir/$repo_name"

    # Ensure repo ownership and permissions
    _cmd "chown -R $user:$user $dest_dir"
    _cmd "chmod -R g+w $dest_dir"
    _cmd "chmod -s $dest_dir"

    # Run installer if specified and executable
    if [[ -n "$installer" && -x "$dest_dir/$installer" ]]; then
      info "Running installer for $repo_name..." "$QUIET"
      sudo -H -u "$user" bash -c "
        export PATH=\"$VENVDIR/bin:\$PATH\"
        $dest_dir/$installer
      "
    elif [[ -n "$installer" ]]; then
      warn "Installer $installer for $repo_name not executable, skipping" "$QUIET"
    fi
  done

  ok "HWGA / no2id setup complete" "$QUIET"
}
