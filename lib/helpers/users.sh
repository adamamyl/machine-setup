#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# Basic / Idempotent User/group creation 
# ---------------------------------------
require_user() {
  local user="$1"

  # Return immediately if user exists
  id "$user" &>/dev/null && return 0

  # Create user safely
  _root_cmd "safe_useradd -m $user" || {
    warn "Failed to create user '$user'"
    return 1
  }

  info "Created user '$user'" "$QUIET"
}

add_user_to_group() {
  local user="$1"
  local group="$2"

  # Verify user exists
  id "$user" &>/dev/null || {
    warn "User '$user' does not exist, cannot add to group '$group'"
    return 1
  }

  # Create group if missing
  getent group "$group" >/dev/null || _root_cmd "safe_groupadd -f $group"

  # Only add if user is not already in the group
  if ! id -nG "$user" | grep -qw "$group"; then
    _root_cmd "safe_usermod -aG $group $user"
  else
    info "User '$user' already in group '$group'" "$QUIET"
  fi
}

# -------------------------------
# User/group and SSH helper functions
# -------------------------------
users_to_groups_if_needed() {
  local user="$1"
  shift
  local groups=("$@")
  _root_cmd "id $user" >/dev/null 2>&1 || _root_cmd "safe_useradd $user -m"
  for group in "${groups[@]}"; do
    _root_cmd "safe_getent group $group || safe_groupadd -f $group"
    _root_cmd "safe_usermod -aG $group $user"
  done
}
  
create_if_needed_ssh_dir() {
  local user="$1"
  local ssh_dir
  ssh_dir="$(eval safe_echo "~$user")/.ssh"
  _root_cmd "safe_mkdir -p -m 700 $ssh_dir"
  _root_cmd "safe_chown $user:$user $ssh_dir"
  safe_echo "$ssh_dir"
}

create_if_needed_ssh_key() {
  local user="$1"
  local ssh_dir="$2"
  local key_name="$3"
  local key_file="$ssh_dir/$key_name"

  if [[ ! -f "$key_file" ]]; then
    info "Generating SSH key for $key_name..." "$QUIET"
    _cmd "ssh-keygen -t ed25519 -f $key_file -N '' -C '${user}@$(hostname)'"
    _cmd "safe_chmod 600 $key_file"
    _cmd "safe_chown $user:$user $key_file"
  fi
}

set_homedir_perms_recursively() {
  local user="$1"
  local dir="$2"
  _root_cmd "safe_chown -R $user:$user $dir"
  _root_cmd "safe_find $dir -type f -exec safe_chmod 644 {} \;"
  _root_cmd "safe_find $dir -type d -exec safe_chmod 755 {} \;"
}

set_ssh_perms() {
  local user="$1"
  local ssh_dir="$2"
  _root_cmd "safe_chmod 700 $ssh_dir"
  _root_cmd "safe_chown $user:$user $ssh_dir"
  _root_cmd "safe_find $ssh_dir -type f -exec safe_chmod 600 {} \;"
}
