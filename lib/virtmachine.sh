#!/usr/bin/env bash
set -euo pipefail

# Default debug flags
DEBUG="${DEBUG:-false}"
DEBUG_LEVEL="${DEBUG_LEVEL:-1}"
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Determine repository root and library directory
# ----------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # one level up from lib/
LIB_DIR="$REPO_ROOT/lib"

# Source debug helper
source "$LIB_DIR/helpers/debug.sh"
# Enable debug if requested via ENV
[[ "$DEBUG" == true ]] && enable_debug "$DEBUG_LEVEL"

# Parse --debug and optional level from CLI
while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
        DEBUG=true
        shift
        if [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]]; then
          DEBUG_LEVEL="$1"
          shift
        else
          DEBUG_LEVEL=1
        fi
        VERBOSE=true  # debug implies verbose
        enable_debug "$DEBUG_LEVEL"
        ;;
    --verbose) VERBOSE=true; shift ;;
    --quiet) QUIET=true; shift ;;
    --user)
        shift
        VM_USER="$1"
        shift
        ;;
    *)
      break
      ;;
  esac
done

# ----------------------------------------------------------------------
# Source helpers
# ----------------------------------------------------------------------
source "$LIB_DIR/helpers/colors.sh"
source "$LIB_DIR/helpers/logging.sh"
source "$LIB_DIR/helpers-extra/apt-behaviour.sh"
source "$LIB_DIR/platform.sh"

# ----------------------------------------------------------------------
# Default VM flags
# ----------------------------------------------------------------------
DRY_RUN=false
QUIET=false
VERBOSE=false
VM_USER=""
DEBUG="${DEBUG:-false}"
DEBUG_LEVEL="${DEBUG_LEVEL:-1}"
# Default VM user if not specified
VM_USER="${VM_USER:-adam}"

# ----------------------------------------------------------------------
# Helper wrapper for dry-run
# ----------------------------------------------------------------------
_cmd() {
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] $*" "$QUIET"
  else
    if [[ "$DEBUG" == true ]]; then
      # Run command with set -o errexit so failures are caught
      eval "$@" || {
          err "Command failed: $*"
          return 1
        }
    else
      eval "$@"
    fi
  fi
}

# ----------------------------------------------------------------------
# Require root
# ----------------------------------------------------------------------
require_root() {
  if [[ $(id -u) -ne 0 ]]; then
    err "Must be run as root"
    exit 1
  fi
}
require_root

info "Starting virtual machine setup..." "$QUIET"

# ----------------------------------------------------------------------
# Detect if running in a VM
# ----------------------------------------------------------------------
VM_TYPE=$(systemd-detect-virt || true)
if [[ -z "$VM_TYPE" ]]; then
  if command -v dmidecode &>/dev/null; then
    VM_TYPE=$(dmidecode -s system-product-name || true)
  elif command -v lshw &>/dev/null; then
    VM_TYPE=$(lshw -class system 2>/dev/null | grep "product" || true)
  fi
fi

if [[ -n "$VM_TYPE" ]]; then
  ok "Virtual machine detected: $VM_TYPE" "$QUIET"
else
  warn "No VM detected. Exiting." "$QUIET"
  exit 0
fi

# ----------------------------------------------------------------------
# Create mount directory
# ----------------------------------------------------------------------
UTM_MOUNT="/mnt/utm"
if [[ ! -d "$UTM_MOUNT" ]]; then
  _cmd "mkdir -p $UTM_MOUNT"
  _cmd "chown $VM_USER:$VM_USER $UTM_MOUNT"
else
  info "$UTM_MOUNT already exists" "$QUIET"
fi

# ----------------------------------------------------------------------
# Install guest packages if missing
# ----------------------------------------------------------------------
for pkg in spice-vdagent qemu-guest-agent bindfs; do
  if ! dpkg -s "$pkg" &>/dev/null; then
    apt_install "$pkg"
  else
    info "$pkg already installed" "$QUIET"
  fi
done

# ----------------------------------------------------------------------
# Fix black screen boot issue if NetworkManager-wait-online and
# systemd-networkd-wait-online both enabled
# ----------------------------------------------------------------------
for svc in NetworkManager-wait-online.service systemd-networkd-wait-online.service; do
  if systemctl is-enabled "$svc" &>/dev/null; then
    info "$svc is enabled" "$QUIET"
  fi
done

# If both enabled, disable systemd-networkd
if systemctl is-enabled NetworkManager-wait-online.service &>/dev/null \
   && systemctl is-enabled systemd-networkd-wait-online.service &>/dev/null; then
  _cmd "systemctl disable systemd-networkd.service"
fi

# ----------------------------------------------------------------------
# Ensure fstab entry exists
# ----------------------------------------------------------------------
FSTAB_LINE="share $UTM_MOUNT 9p trans=virtio,version=9p2000.L,rw,_netdev,nofail,auto 0 0"
if ! grep -qF "$FSTAB_LINE" /etc/fstab; then
  _cmd bash -c "echo '$FSTAB_LINE' >> /etc/fstab"
fi

ok "Virtual machine setup completed ✅" "$QUIET"
