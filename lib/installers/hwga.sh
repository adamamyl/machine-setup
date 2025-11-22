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

# Source Python helper and GitHub deploy key helper
source "$LIB_DIR/helpers/python.sh"
source "$LIB_DIR/installers/github-deploy-key.sh"

setup_repo() {
  local repo_url="$1"
  local dest_dir="$2"
  local user="$3"
  local installer="$4"
  local key_file="$5"

  # Clone/update repo with optional deploy key
  clone_or_update_repo "$repo_url" "$dest_dir" "$key_file"

  _cmd "chown -R $user:$user $dest_dir"
  _cmd "chmod -R g+w $dest_dir"
  _cmd "chmod -s $dest_dir"

  if [[ -n "$installer" && -x "$dest_dir/$installer" ]]; then
    info "Running installer $installer..."
    _cmd "$dest_dir/$installer"
  fi
}

setup_hwga_no2id() {
  info "Starting HWGA / no2id setup..." "$QUIET"

  # Ensure group exists and base dir is writable
  groupadd -f docker
  _cmd "mkdir -p $HWGA_DIR"
  _cmd "chgrp docker $HWGA_DIR"
  _cmd "chmod g+w $HWGA_DIR"
  _cmd "chmod -s $HWGA_DIR"

  for repo_name in "${!HWGA_REPOS[@]}"; do
    IFS=':' read -r user dest_dir installer <<< "${HWGA_REPOS[$repo_name]}"
    local ssh_dir
    ssh_dir="$(eval echo "~$user")/.ssh"
    local key_file="$ssh_dir/$repo_name"

    require_user "$user"
    add_user_to_group "$user" docker

    _cmd "mkdir -p -m 700 $ssh_dir"
    _cmd "chown $user:$user $ssh_dir"

    # Generate deploy key if missing
    if [[ ! -f "$key_file" ]]; then
      info "Generating SSH key for $repo_name..."
      _cmd "ssh-keygen -t ed25519 -f $key_file -N '' -C '${user}@$(hostname)'"
      _cmd "chmod 600 $key_file"
      _cmd "chown $user:$user $key_file"
    fi

    # Determine repo URL
    local repo_url
    [[ "$repo_name" == "herewegoagain" ]] && repo_url="$NO2ID_REPO" || repo_url="$FAKE_LE_REPO"

    # Deploy key workflow using Python inside venv
    sudo -u "$user" run_github_deploy_key "$repo_url" "$key_file"

    # Clone or update repo and run installer
    setup_repo "$repo_url" "$dest_dir" "$user" "$installer" "$key_file"
  done

  ok "HWGA / no2id setup complete" "$QUIET"
}
