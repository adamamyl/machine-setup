#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
is_mac=false
is_linux=false

case "$OS" in
  darwin) is_mac=true ;;
  linux) is_linux=true ;;
  *) err "Unsupported OS: $OS"; exit 1 ;;
esac

DISPLAY_VAR="${DISPLAY:-}"

is_ubuntu_desktop() {
  [[ "$is_linux" == true && -n "$DISPLAY_VAR" && -x "$(command -v gnome-shell)" ]]
}

platform_info() {
  echo "OS: $OS"
  echo "Mac: $is_mac"
  echo "Linux: $is_linux"
  echo "Ubuntu Desktop: $(is_ubuntu_desktop && echo yes || echo no)"
}
