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

  # Avoid unnecessary mkdir if it already exists
  if [[ -d "$dir" ]]; then
    info "Ensured directory exists: $dir"
    return 0
  fi

  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] mkdir -p $dir"
    return 0
  fi

  # Use the safe mkdir wrapper (automatically logs, checks, DRY_RUN aware)
  safe_mkdir -p "$dir"

  info "Ensured directory exists: $dir"
}

# Wrapper to ensure a path exists before running a command
# Usage: with_dir "/path/to/dir" some_command arg1 arg2 ...
with_dir() {
  local dir="$1"
  shift
  local cmd=("$@")

  if [[ -z "$dir" ]]; then
    err "with_dir called with empty directory path"
    return 1
  fi

  # Ensure directory exists (safe)
  ensure_dir "$dir" || return $?

  # No command? Just ensure the directory exists and exit successfully.
  if [[ ${#cmd[@]} -eq 0 ]]; then
    info "Directory ensured: $dir (no command executed)"
    return 0
  fi

  # DRY-RUN mode: log what *would* be run
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] (cd $dir && ${cmd[*]})"
    return 0
  fi

  # Execute inside directory in a subshell so caller’s PWD is not altered
  (
    cd "$dir" || {
      err "Failed to cd into: $dir"
      exit 1
    }

    "${cmd[@]}"
  )
}
 
# Provides "safe_" wrappers for system commands to add logging, 
# DRY_RUN support, and path checks.

# ------------------------
# Directory & Path Safety Helpers
# ------------------------
ensure_path_exists() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    mkdir -p "$path"
    info "Created missing path: $path"
  fi
}

ensure_dir_writable() {
  local dir="$1"
  if [[ ! -w "$dir" ]]; then
    warn "Directory not writable: $dir"
    return 1
  fi
}

# ------------------------
# Special Handling Commands
# ------------------------

# Usage: safe_mkdir [-p] "/path/to/dir"
safe_mkdir() {
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] mkdir $*"
  else
    mkdir "$@"
    info "Executed mkdir $*"
  fi
}
alias mkdir='safe_mkdir'

# Usage: safe_chown "user:group" "/path/to/dir_or_file"
safe_chown() {
  local owner="$1"
  local target="$2"
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] chown $owner $target"
  else
    chown "$owner" "$target"
    info "Executed chown $owner $target"
  fi
}
alias chown='safe_chown'

# Usage: safe_chmod "flags" "/path/to/dir_or_file"
safe_chmod() {
  local flags="$1"
  local target="$2"
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] chmod $flags $target"
  else
    chmod "$flags" "$target"
    info "Executed chmod $flags $target"
  fi
}
alias chmod='safe_chmod'

# ------------------------
# Simple commands that don't need special flag handling
# ------------------------
simple_commands=(touch date ln pwd sleep whoami echo)

for cmd in "${simple_commands[@]}"; do
  eval "
    safe_$cmd() {
      if [[ \"\$DRY_RUN\" == true ]]; then
        info \"[DRY-RUN] $cmd \$*\"
      else
        $cmd \"\$@\"
        info \"Executed $cmd: \$*\"
      fi
    }
    alias $cmd='safe_$cmd'
  "
done

# ------------------------
# Aliases helper
# ------------------------
# Now any call to the original command will go through the safe wrapper.
# Example: mkdir -> safe_mkdir, touch -> safe_touch, etc.
