#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ===============================
# Directory & Path Safety Helpers
# ===============================
# These helpers wrap common filesystem commands with logging,
# DRY-RUN support, and colored/emoji output.

# Safely create a directory if it does not exist
# Usage: ensure_dir "/path/to/dir"
ensure_dir() {
  local dir="$1"
  if [[ -z "$dir" ]]; then
    err "ensure_dir called with empty path"
    return 1
  fi

  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] mkdir -p $dir"
  else
    [[ -d "$dir" ]] || mkdir -p "$dir"
    info "Ensured directory exists: $dir"
  fi
}

# Safely remove a directory or file
# Usage: safe_rm "/path/to/file_or_dir"
safe_rm() {
  local target="$1"
  if [[ -z "$target" ]]; then
    err "safe_rm called with empty path"
    return 1
  fi

  if [[ "$DRY_RUN" == true ]]; then
    warn "[DRY-RUN] rm -rf $target"
  else
    [[ -e "$target" ]] && rm -rf "$target"
    warn "Removed: $target"
  fi
}

# Safely change ownership
# Usage: safe_chown "user:group" "/path/to/dir_or_file"
safe_chown() {
  local owner="$1"
  local target="$2"

  if [[ -z "$owner" || -z "$target" ]]; then
    err "safe_chown requires owner and target"
    return 1
  fi

  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] chown $owner $target"
  else
    chown "$owner" "$target"
    info "Changed ownership: $owner -> $target"
  fi
}

# Safely change permissions
# Usage: safe_chmod "755" "/path/to/file_or_dir"
safe_chmod() {
  local perms="$1"
  local target="$2"

  if [[ -z "$perms" || -z "$target" ]]; then
    err "safe_chmod requires permissions and target"
    return 1
  fi

  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] chmod $perms $target"
  else
    chmod "$perms" "$target"
    info "Set permissions: $perms -> $target"
  fi
}

# Wrapper to ensure a path exists before running a command
# Usage: with_dir "/path/to/dir" some_command arg1 arg2 ...
with_dir() {
  local dir="$1"
  shift
  local cmd=("$@")

  ensure_dir "$dir"
  if [[ ${#cmd[@]} -gt 0 ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      info "[DRY-RUN] (inside $dir) ${cmd[*]}"
    else
      (cd "$dir" && "${cmd[@]}")
    fi
  fi
}
