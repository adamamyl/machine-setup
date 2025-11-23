#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOTSRC_CHECKOUT="/usr/local/src"

declare -A HWGA_REPOS=(
  ["herewegoagain"]="no2id-docker:$ROOTSRC_CHECKOUT/herewegoagain:install"
  ["fake-le"]="adam:$ROOTSRC_CHECKOUT/fake-le:fake-le-for-no2id-docker-installer"
)

NO2ID_REPO="git@github.com:no2id/herewegoagain.git"
FAKE_LE_REPO="git@github.com:adamamyl/fake-le.git"

# Source helpers dynamically, avoiding double /lib
USER_HELPERS="$LIB_DIR/helpers/users.sh"
[[ -f "$USER_HELPERS" ]] || { echo "Cannot find users.sh"; exit 1; }
source "$USER_HELPERS"

display_key_and_url_for_each_repo() {
  local user="$1"
  local ssh_dir="$2"
  local repo_name="$3"
  local repo_url="$4"

  info "Add the following public key as a deploy key to $repo_url for $repo_name:"
  cat "$ssh_dir/$repo_name.pub"
  echo
  info "Deploy key URL: $repo_url"
  read -p "Press Enter once added..."
}

clone_repo() {
  local user="$1"
  local ssh_key="$2"
  local repo_url="$3"
  local dest_dir="$4"
  local extra_opts="${5:-}"

  clone_or_update_repo "$repo_url" "$dest_dir" "$ssh_key" "$extra_opts"
}

setup_hwga() {
  info "Starting HWGA setup..." "$QUIET"
  _root_cmd safe_groupadd -f docker

  for repo_name in "${!HWGA_REPOS[@]}"; do
    IFS=':' read -r user dest_dir installer <<< "${HWGA_REPOS[$repo_name]}"

    # Add user to groups
    local groups=(docker)
    [[ "$user" == "adam" ]] && groups+=(staff)
    users_to_groups_if_needed "$user" "${groups[@]}"

    # Ensure base dir
    _root_cmd "safe_mkdir -p $ROOTSRC_CHECKOUT"
    _root_cmd "safe_chgrp docker $ROOTSRC_CHECKOUT"
    _root_cmd "safe_chmod g+w $ROOTSRC_CHECKOUT"
    _root_cmd "safe_chmod -s $ROOTSRC_CHECKOUT"

    ssh_dir=$(create_if_needed_ssh_dir "$user")
    create_if_needed_ssh_key "$user" "$ssh_dir" "$repo_name"

    # Determine repo URL
    local repo_url="$NO2ID_REPO"
    [[ "$repo_name" != "herewegoagain" ]] && repo_url="$FAKE_LE_REPO"

    display_key_and_url_for_each_repo "$user" "$ssh_dir" "$repo_name" "$repo_url"
    clone_repo "$user" "$ssh_dir/$repo_name" "$repo_url" "$dest_dir" "--recursive"
    set_homedir_perms_recursively "$user" "$dest_dir"
    set_ssh_perms "$user" "$ssh_dir"

    # Run installer if exists
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

  ok "HWGA setup complete" "$QUIET"
}
