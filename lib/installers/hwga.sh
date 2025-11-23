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

# Ensure users.sh is sourced
source /usr/local/src/machine-setup/lib/helpers/users.sh

setup_hwga_no2id() {
  info "Starting HWGA / no2id setup..." "$QUIET"

  # Ensure docker group exists
  groupadd -f docker

  # Ensure required users exist and are added to docker group
  for u in no2id-docker adam; do
    require_user "$u"
    add_user_to_group "$u" docker
  done

  # Ensure base HWGA directory exists and is group writable
  _cmd "mkdir -p $HWGA_DIR"
  _cmd "chgrp docker $HWGA_DIR"
  _cmd "chmod g+w $HWGA_DIR"
  _cmd "chmod -s $HWGA_DIR"

  for repo_name in "${!HWGA_REPOS[@]}"; do
    IFS=':' read -r user dest_dir installer <<< "${HWGA_REPOS[$repo_name]}"
    ssh_dir="$(eval echo "~$user")/.ssh"

    # Ensure SSH directory exists
    _cmd "mkdir -p -m 700 $ssh_dir"
    _cmd "chown $user:$user $ssh_dir"

    # Generate deploy key if missing
    if [[ ! -f "$ssh_dir/$repo_name" ]]; then
      info "Generating SSH key for $repo_name..." "$QUIET"
      _cmd "ssh-keygen -t ed25519 -f $ssh_dir/$repo_name -N '' -C '${user}@$(hostname)'"
      _cmd "chmod 600 $ssh_dir/$repo_name"
      _cmd "chown $user:$user $ssh_dir/$repo_name"
    fi

    # Show deploy key instructions
    if [[ "$repo_name" == "herewegoagain" ]]; then
      info "Ensure this public key is added to git.amyl.org.uk (user hendricks) for repo $repo_name:"
    else
      info "Ensure this public key is added to GitHub for repo $repo_name:"
    fi
    cat "$ssh_dir/$repo_name.pub"
    read -p "Press Enter once added..."

    # Determine repo URL
    repo_url="$NO2ID_REPO"
    [[ "$repo_name" != "herewegoagain" ]] && repo_url="$FAKE_LE_REPO"

    # Run Python deploy key script using venv
    run_github_deploy_key "$repo_url" "$ssh_dir/$repo_name"

    # Clone or update repo using deploy key (recursive)
    clone_or_update_repo "$repo_url" "$dest_dir" "$ssh_dir/$repo_name" "--recursive"

    # Ensure repo ownership and permissions
    _cmd "chown -R $user:$user $dest_dir"
    _cmd "chmod -R g+w $dest_dir"
    _cmd "chmod -s $dest_dir"

    # Run installer if specified and executable
    if [[ -n "$installer" && -x "$dest_dir/$installer" ]]; then
      info "Running installer for $repo_name..." "$QUIET"
      sudo -H -u "$user" bash -c '
        set -euo pipefail
        IFS=$'\''\n\t'\''
        export VENVDIR="'"$VENVDIR"'"
        export PATH="'"$VENVDIR"'/bin:$PATH"
        "'"$dest_dir"'/$installer"
      '
    elif [[ -n "$installer" ]]; then
      warn "Installer $installer for $repo_name not executable, skipping" "$QUIET"
    fi
  done

  ok "HWGA / no2id setup complete" "$QUIET"
}
