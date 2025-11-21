#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$REPO_ROOT/lib"
TOOLS_DIR="$REPO_ROOT/tools"

DRY_RUN=false
FORCE=false
VERBOSE=false
QUIET=false

# Feature flags
DO_PSEUDOHOME=false
DO_TAILSCALE=false
DO_DOCKER=false
DO_HWGA=false
DO_CLOUDINIT=false
DO_ALL_THE_PACKAGES=false
DO_ALL=false

source "$LIB_DIR/colors.sh"
source "$LIB_DIR/platform.sh"
source "$LIB_DIR/users.sh"
source "$LIB_DIR/sshkeys.sh"
source "$LIB_DIR/packages.sh"
source "$LIB_DIR/docker.sh"
source "$LIB_DIR/cloud-init.sh"
source "$LIB_DIR/pseudohome.sh"
source "$LIB_DIR/hwga.sh"
source "$LIB_DIR/vscode.sh"
source "$LIB_DIR/tailscale.sh"

require_root() { if [[ $(id -u) -ne 0 ]]; then err "Must be run as root"; exit 1; fi }
check_online() { info "Checking network connectivity..."; if ! ping -c1 -W2 1.1.1.1 >/dev/null 2>&1; then err "No network"; exit 1; fi; ok "Network OK"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help) cat <<EOF
Usage: $0 [--tailscale] [--pseudohome] [--docker] [--hwga] [--cloud-init] [--all]
Global: --dry-run --force --verbose --quiet
EOF
            exit 0 ;;
        --dry-run) DRY_RUN=true ;; --force) FORCE=true ;; --verbose) VERBOSE=true ;; --quiet) QUIET=true ;;
        --pseudohome) DO_PSEUDOHOME=true ;; --tailscale) DO_TAILSCALE=true ;; --docker) DO_DOCKER=true ;; --hwga|--no2id) DO_HWGA=true ;; --cloud-init) DO_CLOUDINIT=true ;; --all) DO_ALL=true ;;
        *) err "Unknown arg $1"; exit 1 ;;
    esac
    shift
done

if [[ "$DO_ALL" == true ]]; then
    DO_PSEUDOHOME=true; DO_TAILSCALE=true; DO_DOCKER=true; DO_HWGA=true; DO_CLOUDINIT=true; DO_ALL_THE_PACKAGES=true
fi

require_root
check_online

install_root_ssh_keys
ensure_python_and_venv

if [[ "$DO_ALL" == true || "$DO_TAILSCALE" == true ]]; then
    install_tailscale
    ensure_tailscale_strict
fi

if [[ "$DO_ALL" == true || "$DO_PSEUDOHOME" == true ]]; then
    setup_pseudohome
fi

if [[ "$DO_ALL_THE_PACKAGES" == true ]]; then
    install_packages
fi

if [[ "$DO_ALL" == true || "$DO_DOCKER" == true ]]; then
    install_docker_and_add_users
fi

if [[ "$DO_ALL" == true || "$DO_CLOUDINIT" == true ]]; then
    install_cloud_init_repo
fi

if [[ "$DO_ALL" == true || "$DO_HWGA" == true ]]; then
    setup_hwga_no2id
fi

if [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
    install_vscode
fi

ok "All requested tasks completed."
