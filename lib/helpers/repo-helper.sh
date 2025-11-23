#!/usr/bin/env bash
set -euo pipefail

# clone_or_update_repo <repo_url> <dest_dir> [ssh_priv_key]
clone_or_update_repo() {
  local repo_url="$1"
  local dest_dir="$2"
  local ssh_key="${3:-}"

  # Ensure parent dir exists and is group writable
  _cmd "safe_mkdir -p $(dirname "$dest_dir")"
  _cmd "safe_chgrp -R safe_docker $(dirname "$dest_dir") || true"
  _cmd "safe_chmod -R g+w $(dirname "$dest_dir")"
  _cmd "safe_chmod -R -s $(dirname "$dest_dir") || true"

  if [[ -d "$dest_dir/.git" ]]; then
    # Repo integrity check
    if ! safe_git -C "$dest_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      warn "Corrupted repo at $dest_dir; removing and recloning" "$QUIET"
      _cmd "safe_rm -rf $dest_dir"
    else
      info "Updating $dest_dir" "$QUIET"
      if [[ -n "$ssh_key" ]]; then
        _cmd "GIT_SSH_COMMAND='ssh -i $ssh_key -o IdentitiesOnly=yes' safe_git -C '$dest_dir' fetch --all --prune"
        if [[ $? -ne 0 ]]; then
          warn "Fetch failed for $dest_dir, recloning" "$QUIET"
          _cmd "safe_rm -rf $dest_dir"
        fi
      else
        _cmd "safe_git -C '$dest_dir' fetch --all --prune"
        if [[ $? -ne 0 ]]; then
          warn "Fetch failed for $dest_dir, recloning" "$QUIET"
          _cmd "safe_rm -rf $dest_dir"
        fi
      fi
    fi
  fi

  # Clone if missing
  if [[ ! -d "$dest_dir/.git" ]]; then
    info "Cloning $repo_url -> $dest_dir" "$QUIET"
    if [[ -n "$ssh_key" ]]; then
      _cmd "GIT_SSH_COMMAND='ssh -i $ssh_key -o IdentitiesOnly=yes' safe_git clone '$repo_url' '$dest_dir'"
    else
      _cmd "safe_git clone '$repo_url' '$dest_dir'"
    fi
  fi
}
