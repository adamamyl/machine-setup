#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'


# Source helpers dynamically, avoiding double /lib
USER_HELPERS="$LIB_DIR/helpers/users.sh"
HWGA_HELPERS="$LIB_DIR/installers/hwga.sh"

[[ -f "$USER_HELPERS" ]] || { echo "Cannot find users.sh"; exit 1; }
[[ -f "$HWGA_HELPERS" ]] || { echo "Cannot find hwga.sh"; exit 1; }

source "$USER_HELPERS"
source "$HWGA_HELPERS"

setup_pseudohome() {
  local user="adam"
  local dest_dir="/home/$user/pseudohome"
  local repo_name="pseudohome"
  local repo_url="adam@git.amyl.org.uk:/data/git/pseudoadam"

  users_to_groups_if_needed "$user" docker staff
  ssh_dir=$(create_if_needed_ssh_dir "$user")
  create_if_needed_ssh_key "$user" "$ssh_dir" "$repo_name"
  display_key_and_url_for_each_repo "$user" "$ssh_dir" "$repo_name" "$repo_url"

  clone_repo "$user" "$ssh_dir/$repo_name" "$repo_url" "$dest_dir" "--recursive"
  set_homedir_perms_recursively "$user" "$dest_dir"
  set_ssh_perms "$user" "$ssh_dir"

  local installer="$dest_dir/pseudohome-symlinks"
  if [[ -x "$installer" ]]; then
    info "Running pseudohome installer script..." "$QUIET"
    sudo -H -u "$user" bash -c '
      set -euo pipefail
      IFS=$'\''\n\t'\''
      export VENVDIR="'"$VENVDIR"'"
      export PATH="'"$VENVDIR"'/bin:$PATH"
      "'"$installer"'"
    '
  fi

  ok "Pseudohome setup complete for $user" "$QUIET"
}
