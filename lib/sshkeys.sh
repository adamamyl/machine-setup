#!/usr/bin/env bash
set -euo pipefail
install_ssh_keys() {
  local user="$1"
  local url="$2"
  local homedir
  homedir="$(eval echo "~$user")"
  local sshdir="$homedir/.ssh"
  local auth_keys="$sshdir/authorized_keys"
  _cmd "safe_mkdir -p $sshdir"
  _cmd "safe_chmod 700 $sshdir"
  _cmd "safe_chown $user:$user $sshdir"
  if ! safe_curl -fsSL "$url" -o "$auth_keys"; then
    err "Failed to download SSH keys from $url"
    return 1
  fi
  _cmd "safe_chmod 600 $auth_keys"
  _cmd "safe_chown $user:$user $auth_keys"
  ok "Installed SSH keys for $user from $url"
}
install_root_ssh_keys() {
  install_ssh_keys root "https://github.com/adamamyl.keys"
}
