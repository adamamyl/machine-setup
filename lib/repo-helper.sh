#!/usr/bin/env bash
set -euo pipefail
# clone_or_update_repo <repo_url> <dest_dir> [ssh_priv_key]
clone_or_update_repo() {
  local repo_url="$1"
  local dest_dir="$2"
  local ssh_key="${3:-}"
  mkdir -p "$(dirname "$dest_dir")"
  chgrp docker "$(dirname "$dest_dir")" || true
  chmod g+w "$(dirname "$dest_dir")"
  chmod -s "$(dirname "$dest_dir")" || true
  if [[ -d "$dest_dir/.git" ]]; then
    if ! git -C "$dest_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      warn "Corrupted repo detected at $dest_dir; removing and recloning"
      rm -rf "$dest_dir"
    else
      info "Updating $dest_dir"
      if [[ -n "$ssh_key" ]]; then
        GIT_SSH_COMMAND="ssh -i $ssh_key -o IdentitiesOnly=yes" git -C "$dest_dir" fetch --all --prune || { warn "Fetch failed, recloning"; rm -rf "$dest_dir"; }
      else
        git -C "$dest_dir" fetch --all --prune || { warn "Fetch failed, recloning"; rm -rf "$dest_dir"; }
      fi
    fi
  fi
  if [[ ! -d "$dest_dir/.git" ]]; then
    info "Cloning $repo_url -> $dest_dir"
    if [[ -n "$ssh_key" ]]; then
      GIT_SSH_COMMAND="ssh -i $ssh_key -o IdentitiesOnly=yes" git clone "$repo_url" "$dest_dir"
    else
      git clone "$repo_url" "$dest_dir"
    fi
  fi
}
