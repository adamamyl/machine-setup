
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Setup 'adam' user home repository (pseudohome)
# ----------------------------------------------------------------------
setup_pseudohome() {
  local user="adam"
  local dest_dir="/home/$user/pseudohome"
  local repo_url="git@github.com:adamamyl/pseudohome.git"

  require_user "$user"

  info "Setting up pseudohome for $user at $dest_dir..." "$QUIET"

  _cmd "mkdir -p $dest_dir"
  _cmd "chown $user:$user $dest_dir"
  _cmd "chmod 700 $dest_dir"

  # SSH deploy key setup
  local ssh_dir
  ssh_dir="$(eval echo "~$user")/.ssh"
  _cmd "mkdir -p -m 700 $ssh_dir"
  _cmd "chown $user:$user $ssh_dir"

  if [[ ! -f "$ssh_dir/pseudohome" ]]; then
    info "Generating deploy key for pseudohome..." "$QUIET"
    _cmd "ssh-keygen -t ed25519 -f $ssh_dir/pseudohome -N '' -C '${user}@$(hostname)'"
    _cmd "chmod 600 $ssh_dir/pseudohome"
    _cmd "chown $user:$user $ssh_dir/pseudohome"
  fi

  info "Ensure the following public key is added to GitHub:"
  cat "$ssh_dir/pseudohome.pub"
  read -p "Press Enter once added..."

  # Clone or update repo
  clone_or_update_repo "$repo_url" "$dest_dir" "$ssh_dir/pseudohome"

  _cmd "chown -R $user:$user $dest_dir"
  _cmd "chmod -R g+w $dest_dir"
  _cmd "chmod -s $dest_dir"

  # Optionally run post-install script if exists
  local installer="$dest_dir/install.sh"
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
