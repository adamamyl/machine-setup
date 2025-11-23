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
  [[ -d "$dir" ]] && { info "Ensured directory exists: $dir"; return 0; }
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
  [[ -z "$dir" ]] && { err "with_dir called with empty directory path"; return 1; }
  ensure_dir "$dir" || return $?
  [[ ${#cmd[@]} -eq 0 ]] && { info "Directory ensured: $dir (no command executed)"; return 0; }
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] (cd $dir && ${cmd[*]})"
    return 0
  fi
  ( cd "$dir" || { err "Failed to cd into: $dir"; exit 1; }; "${cmd[@]}" )
}

ensure_path_exists() {
  local path="$1"
  [[ ! -e "$path" ]] && { mkdir -p "$path"; info "Created missing path: $path"; }
}

ensure_dir_writable() {
  local dir="$1"
  [[ ! -w "$dir" ]] && { warn "Directory not writable: $dir"; return 1; }
}

# ===============================
# Special Handling Commands
# ===============================

# mkdir, chown, chmod already have custom handling
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
# Simple commands (no path/flags handling)
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
# Additional SAFE_CMDS needing generic wrappers
# ------------------------
# Commands: rm, rmdir, cp, mv, curl, wget, tar, unzip, git, docker, systemctl, groupadd, useradd, passwd

# Path or file aware commands
file_commands=(rm rmdir cp mv)
for cmd in "${file_commands[@]}"; do
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

# Network / system / other commands
other_commands=(curl wget tar unzip git docker systemctl groupadd useradd passwd)
for cmd in "${other_commands[@]}"; do
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
