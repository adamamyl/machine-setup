#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$REPO_ROOT/lib"
TOOLS_DIR="$REPO_ROOT/tools"

# Global flags
DRY_RUN=false
FORCE=false
VERBOSE=false
QUIET=false
DO_CHECK_ONLINE=false
DO_AUTOREMOVE=true
VENVDIR="/opt/setup-venv"
export VENVDIR

# Global debug-subshell flag
DEBUG_SUBSHELL=false
export DEBUG_SUBSHELL

# ----------------------------------------------------------------------
# Global flag for enabling verbose sudo subshells
# ----------------------------------------------------------------------
DEBUG_SUBSHELL=false
export DEBUG_SUBSHELL

# Module flags
DO_PSEUDOHOME=false
DO_TAILSCALE=false
DO_DOCKER=false
DO_HWGA=false
DO_CLOUDINIT=false
DO_ALL_THE_PACKAGES=false
DO_SUDOERS=false
DO_ALL=false
VM_FLAG=false
VM_USER=""

# ----------------------------------------------------------------------
# Source library scripts by category
# ----------------------------------------------------------------------

# Source debug library first to enable debug early
source "$LIB_DIR/helpers/debug.sh"

# Helpers first
for f in "$LIB_DIR/helpers/"*.sh; do
  [[ -f "$f" ]] && source "$f"
done

# Extra helpers
for f in "$LIB_DIR/helpers-extra/"*.sh; do
  [[ -f "$f" ]] && source "$f"
done

# Installers / modules
for f in "$LIB_DIR/installers/"*.sh; do
  [[ -f "$f" ]] && source "$f"
done

# Individual scripts in lib root
source "$LIB_DIR/sudoers.sh"
source "$LIB_DIR/installers/github-deploy-key.sh"
source "$LIB_DIR/sshkeys.sh"

# Export module functions for sudo subshells
export -f setup_pseudohome
export -f setup_hwga

require_root() { 
  if [[ $(id -u) -ne 0 ]]; then 
    err "Must be run as root"
    exit 1
  fi
}

# ----------------------------------------------------------------------
# Show help
# ----------------------------------------------------------------------
show_help() {
cat <<EOF
Usage: $0 [OPTIONS]

Global options:
    --help                 Show this help
    --dry-run              Log actions without executing
    --force                Overwrite files / skip prompts
    --verbose              Enable verbose output
    --quiet                Minimal output
    --check-online         Verify network connectivity before running
    --skip-network-check   Disable connectivity check (default)
    --no-autoremove        Skip 'apt autoremove' at the end
    --vm | --virtmachine   Run UTM/QEMU virtual machine setup
    --vm-user <username>   Specify local user for UTM mount (default: adam)

Module options:
    --pseudohome           Setup 'adam' user and pseudohome repository
    --sudoers              Install /etc/sudoers.d/staff for NOPASSWD on staff
    --tailscale            Install and configure Tailscale
    --docker               Install Docker and add users to docker group
    --hwga | --no2id       Setup no2id-docker user and deploy keys
    --cloud-init           Install post-cloud-init scripts (Linux only)
    --all-the-packages     Install standard packages & update-all-the-packages
    --all                  Run all tasks
EOF
}

# ----------------------------------------------------------------------
# CLI argument parsing
# ----------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      shift
        if [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]]; then
          DEBUG_LEVEL="$1"
        shift
        else
          DEBUG_LEVEL=1
        fi
      enable_debug "$DEBUG_LEVEL"
      ;;
    --help) show_help; exit 0 ;;
    --dry-run) DRY_RUN=true ;;
    --force) FORCE=true ;;
    --verbose) VERBOSE=true ;;
    --quiet) QUIET=true ;;
    --check-online) DO_CHECK_ONLINE=true ;;
    --skip-network-check) DO_CHECK_ONLINE=false ;;
    --no-autoremove) DO_AUTOREMOVE=false ;;
    --pseudohome) DO_PSEUDOHOME=true ;;
    --sudoers) DO_SUDOERS=true ;;
    --tailscale) DO_TAILSCALE=true ;;
    --docker) DO_DOCKER=true ;;
    --hwga|--no2id) DO_HWGA=true ;;
    --cloud-init) DO_CLOUDINIT=true ;;
    --all-the-packages) DO_ALL_THE_PACKAGES=true ;;
    --all) DO_ALL=true ;;
    --vm|--virtmachine) VM_FLAG=true ;;
    --vm-user)
      shift
      VM_USER="$1"
      ;;
    --debug-subshell)
      DEBUG_SUBSHELL=true
      ;;
    *) err "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

require_root

# ----------------------------------------------------------------------
# Optional network check
# ----------------------------------------------------------------------
[[ "$DO_CHECK_ONLINE" == true ]] && check_online || true

# ----------------------------------------------------------------------
# Root SSH keys + Python/venv
# ----------------------------------------------------------------------
install_root_ssh_keys
ensure_python_and_venv
export VENVDIR="/opt/setup-venv"
export PATH="$VENVDIR/bin:$PATH"

# ----------------------------------------------------------------------
# Build flags array for user-invoked scripts
# ----------------------------------------------------------------------
build_user_flags() {
    local flags=()
    [[ "$DRY_RUN" == true ]] && flags+=("--dry-run")
    [[ "$QUIET" == true ]] && flags+=("--quiet")
    [[ "$VERBOSE" == true ]] && flags+=("--verbose")
    [[ -n "$VM_USER" ]] && flags+=("--user" "$VM_USER")
    printf '%s\n' "${flags[@]}"
}

USER_FLAGS=()
while IFS= read -r flag; do
    USER_FLAGS+=("$flag")
done < <(build_user_flags)

export DRY_RUN QUIET VERBOSE VM_USER USER_FLAGS

# ----------------------------------------------------------------------
# Helper: run a module function as a specified user
# All commands run via this function automatically get safe_* wrappers
# Optional debug block triggered by argument --debug-subshell
# ----------------------------------------------------------------------
run_module_as_user() {
  local user="$1"
  shift

  # Check if --debug-subshell passed, fallback to global DEBUG_SUBSHELL
  local debug_subshell=${DEBUG_SUBSHELL:-false}
  if [[ "$1" == "--debug-subshell" ]]; then
      debug_subshell=true
      shift
  fi

  local module_cmd=("$@")

  if [[ -z "$user" ]]; then
    err "User not specified"
    return 1
  fi

  if [[ ${#module_cmd[@]} -eq 0 ]]; then
    err "No command/function specified"
    return 1
  fi

  # Export environment variables for sudo
  export REPO_ROOT LIB_DIR TOOLS_DIR VENVDIR
  export DRY_RUN="${DRY_RUN:-false}"
  export QUIET="${QUIET:-false}"
  export VERBOSE="${VERBOSE:-false}"

  # Source safe-commands first, to guarantee safe_* functions exist
  [[ -f "$LIB_DIR/helpers/safe-commands.sh" ]] && source "$LIB_DIR/helpers/safe-commands.sh"

  # Capture all shell functions from parent after sourcing safe-commands.sh
  local all_functions
  all_functions="$(declare -f)"

  sudo -H -u "$user" \
    REPO_ROOT="$REPO_ROOT" \
    LIB_DIR="$LIB_DIR" \
    TOOLS_DIR="$TOOLS_DIR" \
    VENVDIR="$VENVDIR" \
    DRY_RUN="$DRY_RUN" \
    QUIET="$QUIET" \
    VERBOSE="$VERBOSE" \
    bash -c '
      set -euo pipefail
      IFS=$'\''\n\t'\''

      # Enable debug if requested
      if [[ "'"$debug_subshell"'" == true ]]; then
        set -x
      fi

      #############################################################################
      # *************************** DEBUG BLOCK START ****************************#
      if [[ "'"$debug_subshell"'" == true ]]; then
        echo "===== DEBUG: Starting sudo subshell for user: '"$user"' =====" >&2
        echo "===== DEBUG: Environment =====" >&2
        env | sort >&2
        echo "===============================" >&2

        for f in "$LIB_DIR/helpers/"*.sh; do
          [[ -f "$f" ]] && echo "DEBUG: sourcing $f" >&2 && source "$f"
        done

        for f in "$LIB_DIR/helpers-extra/"*.sh; do
          [[ -f "$f" ]] && echo "DEBUG: sourcing $f" >&2 && source "$f"
        done

        for f in "$LIB_DIR/installers/"*.sh; do
          [[ -f "$f" ]] && echo "DEBUG: sourcing $f" >&2 && source "$f"
        done

        echo "DEBUG: BASH_SOURCE=${BASH_SOURCE[0]}, FUNCNAME=${FUNCNAME[0]}" >&2
        echo "===== DEBUG: DEBUG BLOCK END =====" >&2
      fi
      #############################################################################

      # Restore all functions from parent
      '"$all_functions"'

      # DRY-RUN mode or actual execution
      if [[ "$DRY_RUN" == true ]]; then
        info "[DRY-RUN] (user: '"$user"') $*"
      else
        if [[ "$debug_subshell" == true ]]; then
          echo "===== DEBUG: Executing command/function: $* =====" >&2
        fi
        "$@"
      fi

      if [[ "$debug_subshell" == true ]]; then
        echo "===== DEBUG: Finished sudo subshell for user: '"$user"' =====" >&2
      fi
    ' _ "${module_cmd[@]}"
}

# ----------------------------------------------------------------------
# Wrapper to run a command as root safely
# Accepts optional --debug-subshell to enable verbose sudo subshell
# ----------------------------------------------------------------------
_root_cmd() {
  local debug_flag=""
  if [[ "$1" == "--debug-subshell" ]]; then
    debug_flag="--debug-subshell"
    shift
  fi
  run_module_as_user root $debug_flag "$@"
}

# ----------------------------------------------------------------------
# Wrapper to run a command as current user safely
# Accepts optional --debug-subshell to enable verbose sudo subshell
# ----------------------------------------------------------------------
_cmd() {
  local debug_flag=""
  if [[ "$1" == "--debug-subshell" ]]; then
    debug_flag="--debug-subshell"
    shift
  fi
  run_module_as_user "$USER" $debug_flag "$@"
}

# ----------------------------------------------------------------------
# Run selected modules in proper order
# ----------------------------------------------------------------------

# Tailscale
[[ "$DO_ALL" == true || "$DO_TAILSCALE" == true ]] && install_tailscale && ensure_tailscale_strict

# Packages
[[ "$DO_ALL_THE_PACKAGES" == true ]] && install_packages

# Docker
[[ "$DO_ALL" == true || "$DO_DOCKER" == true ]] && install_docker_and_add_users

# Linux system repos
[[ "$DO_ALL" == true || "$DO_CLOUDINIT" == true ]] && install_linux_repos

# Sudoers
[[ "$DO_ALL" == true || "$DO_SUDOERS" == true ]] && setup_sudoers_staff "/etc/sudoers.d/staff"

# Run pseudohome as adam user
[[ "$DO_ALL" == true || "$DO_PSEUDOHOME" == true ]] && run_module_as_user "adam" "setup_pseudohome"

# Run HWGA / no2id as no2id-docker user
[[ "$DO_ALL" == true || "$DO_HWGA" == true ]] && run_module_as_user "no2id-docker" "setup_hwga"

# Virtual machine setup
if [[ "$VM_FLAG" == true ]]; then
  info "Running virtual machine setup..." "$QUIET"
  VM_FLAGS=()
  [[ "$DRY_RUN" == true ]] && VM_FLAGS+=("--dry-run")
  [[ "$QUIET" == true ]] && VM_FLAGS+=("--quiet")
  [[ "$VERBOSE" == true ]] && VM_FLAGS+=("--verbose")
  [[ -n "$VM_USER" ]] && VM_FLAGS+=("--user" "$VM_USER")

  "$LIB_DIR/virtmachine.sh" "${VM_FLAGS[@]}"
fi

# Ubuntu desktop extras
if [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
  install_vscode
  install_gnome_tweaks
fi

# Optional apt autoremove
[[ "$DO_AUTOREMOVE" == true ]] && apt_autoremove

ok "All requested tasks completed."
