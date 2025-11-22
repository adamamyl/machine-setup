#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$REPO_ROOT/lib"

# Source helpers
source "$LIB_DIR/colors.sh"
source "$LIB_DIR/logging.sh"
source "$LIB_DIR/platform.sh"

# Default VM flags
DRY_RUN=false
QUIET=false
VERBOSE=false
VM_USER=""

# Parse CLI flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --quiet) QUIET=true ;;
    --verbose) VERBOSE=true ;;
    --user)
      shift
      VM_USER="$1"
      ;;
    *)
      err "Unknown argument to virtmachine.sh: $1"
      exit 1
      ;;
  esac
  shift
done

# Default VM user if not specified
VM_USER="${VM_USER:-adam}"

# Helper wrapper for dry-run
_cmd() {
  if [[ "$DRY_RUN" == true ]]; then
    info "[DRY-RUN] $*" "$QUIET"
  else
    eval "$@"
  fi
}

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
    _cmd "apt update && apt install -y $pkg"
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
  _cmd "echo '$FSTAB_LINE' >> /etc/fstab"
fi

ok "Virtual machine setup completed ✅" "$QUIET"
