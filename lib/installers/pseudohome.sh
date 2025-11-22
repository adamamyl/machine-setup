#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

setup_pseudohome() {
    local user="adam"
    require_user "$user"
    add_user_to_group "$user" staff

    local homedir
    homedir="$(eval echo "~$user")"
    local ssh_dir="$homedir/.ssh"
    _cmd "mkdir -p -m 700 $ssh_dir"
    _cmd "chown $user:$user $ssh_dir"

    # Install SSH keys
    install_ssh_keys "$user" "https://github.com/adamamyl.keys"

    # Clone pseudohome repo
    local repo_url="git@github.com:adamamyl/pseudoadam.git"
    local dest_dir="$homedir/pseudohome"

    if [[ ! -d "$dest_dir" ]]; then
        clone_or_update_repo "$repo_url" "$dest_dir"
        _cmd "chown -R $user:$user $dest_dir"
        _cmd "chmod -R g+w $dest_dir"

        # Run symlink installer inside venv and sudo
        if [[ -x "$dest_dir/pseudohome-symlinks" ]]; then
            info "Running pseudohome symlinks..."
            sudo -H -u "$user" bash -c "
                export PATH=\"$VENVDIR/bin:\$PATH\"
                $dest_dir/pseudohome-symlinks
            "
        else
            warn "Symlink installer not executable"
        fi
    else
        ok "Pseudohome already exists, skipping clone and symlinks"
    fi
}
