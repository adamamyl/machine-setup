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
# Source library scripts by category for consistency
# ----------------------------------------------------------------------

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
source "$LIB_DIR/virtmachine.sh"
source "$LIB_DIR/github-deploy-key.sh"

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

Notes:
------
- For deploying SSH keys to GitHub (e.g., no2id-docker), you may need a Personal Access Token:
  * Classic token: 'repo' scope (full control of private repos)
  * Fine-grained token: select organization, repo access to the repository, "Read & Write" deploy keys
  * Export token as: export GITHUB_TOKEN=ghp_xxxxxxxx
  * GitHub token required if using private or org repositories
  * URL: https://github.com/settings/tokens

- Optional network check can be enabled with --check-online
- Python 3 and virtualenv will be installed automatically if missing (venv at $VENVDIR)
- Each module can be run individually or with --all
- By default, runs 'apt autoremove' at the end; use --no-autoremove to skip

- --vm | --virtmachine
  - Run VM setup for user 'adam' interactively
    - sudo ./setup-machine.sh --vm --vm-user adam --verbose
  - Dry-run only
    - sudo ./setup-machine.sh --vm --dry-run
EOF
}

# ----------------------------------------------------------------------
# CLI argument parsing
# ----------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
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

# ----------------------------------------------------------------------
# Build flags for user-invoked scripts
# ----------------------------------------------------------------------
build_user_flags() {
  local flags=()
  $DRY_RUN && flags+=(--dry-run)
  $QUIET && flags+=(--quiet)
  $VERBOSE && flags+=(--verbose)
  [[ -n "$VM_USER" ]] && flags+=(--user "$VM_USER")
  echo "${flags[@]}"
}
USER_FLAGS=($(build_user_flags))
export DRY_RUN QUIET VERBOSE  # sub-scripts read these

# ----------------------------------------------------------------------
# Run selected modules (order matters)
# ----------------------------------------------------------------------
[[ "$DO_ALL" == true || "$DO_TAILSCALE" == true ]] && install_tailscale && ensure_tailscale_strict
[[ "$DO_ALL_THE_PACKAGES" == true ]] && install_packages
[[ "$DO_ALL" == true || "$DO_DOCKER" == true ]] && install_docker_and_add_users
[[ "$DO_ALL" == true || "$DO_CLOUDINIT" == true ]] && install_linux_repos
[[ "$DO_ALL" == true || "$DO_SUDOERS" == true ]] && setup_sudoers_staff "/etc/sudoers.d/staff"

# Run pseudohome as adam user
[[ "$DO_ALL" == true || "$DO_PSEUDOHOME" == true ]] &&
  sudo -u adam bash -c "PH_FLAGS='${USER_FLAGS[*]}'; setup_pseudohome"

# Run HWGA / no2id as no2id-docker user
[[ "$DO_ALL" == true || "$DO_HWGA" == true ]] &&
  sudo -u no2id-docker bash -c "HWGA_FLAGS='${USER_FLAGS[*]}'; setup_hwga_no2id"

# Virtual machine setup
if [[ "$VM_FLAG" == true ]]; then
  info "Running virtual machine setup..." "$QUIET"
  virtmachine.sh "${USER_FLAGS[@]}"
fi

# Ubuntu desktop extras
if [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
  install_vscode
  install_gnome_tweaks
fi

# Optional apt autoremove
if [[ "$DO_AUTOREMOVE" == true ]]; then
  info "Running apt autoremove..."
  apt_autoremove
fi

ok "All requested tasks completed."
