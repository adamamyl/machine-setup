#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

setup_pseudohome() {
  local user="adam"

  # --- root tasks ---
  _cmd "require_user '$user'"
  _cmd "add_user_to_group '$user' staff"

  local homedir
  homedir="$(eval echo "~$user")"
  local ssh_dir="$homedir/.ssh"

  _cmd "mkdir -p -m 700 '$ssh_dir'"
  _cmd "chown $user:$user '$ssh_dir'"

  # Install SSH keys as root
  _cmd "install_ssh_keys '$user' 'https://github.com/adamamyl.keys'"

  # --- user tasks ---
  local repo_url="git@github.com:adamamyl/pseudoadam.git"
  local dest_dir="$homedir/pseudohome"

  if [[ ! -d "$dest_dir" ]]; then
    _cmd "sudo -H -u '$user' bash -c '
      set -euo pipefail
      IFS=$'\''\n\t'\''
      export PATH=\"$VENVDIR/bin:\$PATH\"

      # Clone repository if missing
      if [[ ! -d \"$dest_dir\" ]]; then
        git clone \"$repo_url\" \"$dest_dir\"
      fi

      chown -R $user:$user \"$dest_dir\"
      chmod -R g+w \"$dest_dir\"

      # Run symlink installer if executable
      if [[ -x \"$dest_dir/pseudohome-symlinks\" ]]; then
        \"$dest_dir/pseudohome-symlinks\"
      fi
    '"
  else
    _cmd "echo 'Pseudohome already exists, skipping clone and symlinks'"
  fi
}
