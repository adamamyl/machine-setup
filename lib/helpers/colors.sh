#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Color codes
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
MAGENTA="\033[0;35m"
CYAN="\033[0;36m"
RESET="\033[0m"

# Emoji prefixes
EMOJI_OK="✅"
EMOJI_INFO="ℹ️"
EMOJI_WARN="⚠️"
EMOJI_ERR="❌"

# Info messages (with optional quiet flag)
info() {
  local quiet="${2:-false}"
  if [[ "$quiet" != true ]]; then
    echo -e "ℹ️  \033[1;34m$*\033[0m"
  fi
}

# Warning messages (optional quiet)
warn() {
  local quiet="${2:-false}"
  if [[ "$quiet" != true ]]; then
    echo -e "⚠️  \033[1;33m$*\033[0m"
  fi
}

# Error messages (optional quiet)
err() {
  local quiet="${2:-false}"
  if [[ "$quiet" != true ]]; then
    echo -e "❌ \033[1;31m$*\033[0m" >&2
  fi
}

# OK messages (optional quiet)
ok() {
  local quiet="${2:-false}"
  if [[ "$quiet" != true ]]; then
    echo -e "✅ \033[1;32m$*\033[0m"
  fi
}

# Debug messages (verbose only)
debug() {
  local verbose="${2:-false}"
  if [[ "$verbose" == true ]]; then
    echo -e "💜 DEBUG: $*"
  fi
}
