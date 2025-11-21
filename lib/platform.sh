#!/usr/bin/env bash
set -euo pipefail

# Detect platform
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

is_mac=false
is_linux=false
is_ubuntu_desktop=false

case "$OS" in
  darwin) is_mac=true ;;
  linux) is_linux=true ;;
  *)
    echo "Unsupported OS: $OS" >&2
    exit 1
    ;;
esac

# Safely check DISPLAY for Linux desktop detection
DISPLAY_VAR="${DISPLAY:-}"  # empty string if not set

# Function to detect Ubuntu desktop environment
is_ubuntu_desktop() {
  if [[ "$is_linux" == true ]] && command -v gnome-shell >/dev/null 2>&1 && [[ -n "$DISPLAY_VAR" ]]; then
    return 0  # true
  else
    return 1  # false
  fi
}

# Optional helper functions
platform_info() {
  echo "OS: $OS"
  echo "Mac: $is_mac"
  echo "Linux: $is_linux"
  if is_ubuntu_desktop; then
    echo "Ubuntu Desktop: yes"
  else
    echo "Ubuntu Desktop: no"
  fi
}
