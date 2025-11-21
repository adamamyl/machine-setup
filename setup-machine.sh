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

# Module flags
DO_PSEUDOHOME=false
DO_TAILSCALE=false
DO_DOCKER=false
DO_HWGA=false
DO_CLOUDINIT=false
DO_ALL_THE_PACKAGES=false
DO_ALL=false

# Source modules
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
source "$LIB_DIR/tweaks.sh"
source "$LIB_DIR/tailscale.sh"
source "$LIB_DIR/python.sh"

require_root() { if [[ $(id -u) -ne 0 ]]; then err "Must be run as root"; exit 1; fi }

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

Module options:
    --pseudohome           Setup 'adam' user and pseudohome repository
    --tailscale            Install and configure Tailscale
    --docker               Install Docker and add users to docker group
    --hwga | --no2id       Setup no2id-docker user and deploy keys
    --cloud-init           Install post-cloud-init scripts (Linux only)
    --all-the-packages     Install standard packages
    --all                  Run all tasks

Notes:
------
- For deploying SSH keys to GitHub (e.g. no2id-docker), you need a Personal Access Token:
  * Classic token: 'repo' scope (full control of private repos)
  * Fine-grained token: select organization, repo access to the repository, "Read & Write" deploy keys
  * Export token as: export GITHUB_TOKEN=ghp_xxxxxxxx
  * GitHub token required if using private or org repositories
  * URL: https://github.com/settings/tokens

- Optional network check can be enabled with --check-online
- Python 3 and virtualenv will be installed automatically if missing
- Each module can be run individually or with --all
- By default, runs 'apt autoremove' at the end; use --no-autoremove to skip
EOF
}

# CLI parsing
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
        --tailscale) DO_TAILSCALE=true ;;
        --docker) DO_DOCKER=true ;;
        --hwga|--no2id) DO_HWGA=true ;;
        --cloud-init) DO_CLOUDINIT=true ;;
        --all-the-packages) DO_ALL_THE_PACKAGES=true ;;
        --all) DO_ALL=true ;;
        *) err "Unknown argument: $1"; exit 1 ;;
    esac
    shift
done

require_root

# Optional network check
[[ "$DO_CHECK_ONLINE" == true ]] && check_online

# Install root SSH keys and Python venv
install_root_ssh_keys
ensure_python_and_venv

# Run selected modules
[[ "$DO_ALL" == true || "$DO_TAILSCALE" == true ]] && install_tailscale && ensure_tailscale_strict
[[ "$DO_ALL" == true || "$DO_PSEUDOHOME" == true ]] && setup_pseudohome
[[ "$DO_ALL_THE_PACKAGES" == true ]] && install_packages
[[ "$DO_ALL" == true || "$DO_DOCKER" == true ]] && install_docker_and_add_users
[[ "$DO_ALL" == true || "$DO_CLOUDINIT" == true ]] && install_cloud_init_repo
[[ "$DO_ALL" == true || "$DO_HWGA" == true ]] && setup_hwga_no2id

# Ubuntu desktop extras
if [[ "$(uname -s)" == "Linux" && is_ubuntu_desktop ]]; then
    install_vscode
    install_gnome_tweaks
fi

# Optional apt autoremove
if [[ "$DO_AUTOREMOVE" == true ]]; then
    info "Running apt autoremove..."
    apt autoremove -y
fi

ok "All requested tasks completed."
