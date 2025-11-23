
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Setup 'adam' user home repository (pseudohome)
# ----------------------------------------------------------------------
setup_pseudohome() {
local user="adam"
local dest_dir="/home/$user/pseudohome"
local repo_name="pseudohome"
local repo_url="adam@git.amyl.org.uk:/data/git/pseudoadam"
local ssh_dir
ssh_dir="$(eval echo "~$user")/.ssh"

require_user "$user"
add_user_to_group "$user" docker
add_user_to_group "$user" staff


_cmd "mkdir -p $ssh_dir -m 700"
_cmd "chown $user:$user $ssh_dir"

# Generate deploy key if missing
if [[ ! -f "$ssh_dir/$repo_name" ]]; then
  info "Generating SSH key for $repo_name..." "$QUIET"
  _cmd "ssh-keygen -t ed25519 -f $ssh_dir/$repo_name -N '' -C '${user}@$(hostname)'"
  _cmd "chmod 600 $ssh_dir/$repo_name"
  _cmd "chown $user:$user $ssh_dir/$repo_name"
fi

# Inform user to add key
info "Add the following public key as a deploy key to git.amyl.org.uk (hendricks user) for $repo_name:"
cat "$ssh_dir/$repo_name.pub"
echo
info "Deploy key URL: git@git.amyl.org.uk:/data/git/pseudoadam"
read -p "Press Enter once added..."

# Clone/update repo recursively
clone_or_update_repo "$repo_url" "$dest_dir" "$ssh_dir/$repo_name" "--recursive"

_cmd "chown -R $user:$user $dest_dir"
_cmd "chmod -R g+w $dest_dir"
_cmd "chmod -s $dest_dir"

# Run post-install script if exists
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
