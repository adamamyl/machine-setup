#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# DEBUG SYSTEM
# ----------------------------------------------------------------------
# Usage:
#   enable_debug [LEVEL]
#   LEVEL: 1=basic, 2=stderr capture, 3=file+line PS4, 4=full set -v

DEBUG="${DEBUG:-false}"
DEBUG_LEVEL="${DEBUG_LEVEL:-1}"

# ANSI for errors
RED="\033[0;31m"
RESET="\033[0m"
EMOJI_ERR="❌"

enable_debug() {
  local level="${1:-1}"
  DEBUG=true
  DEBUG_LEVEL="$level"
  VERBOSE=true

  case "$level" in
    1)
      # Basic set -x
      set -x
      ;;
    2)
      # Trace with stderr capture
      BASH_XTRACEFD=3
      exec 3> >(while IFS= read -r line; do echo "$line"; done)
      set -x
      ;;
    3)
      # Enhanced PS4
      export PS4='+ ${BASH_SOURCE}:${LINENO}: '
      set -x
      ;;
    4)
      # Full trace including lines as read
      export PS4='+ ${BASH_SOURCE}:${LINENO}: '
      set -xv
      ;;
    *)
      echo "Unknown debug level $level, using 1"
      set -x
      ;;
  esac

  # Trap errors to highlight them in red
  trap 'errcode=$?; [[ $errcode -ne 0 ]] && echo -e "${RED}${EMOJI_ERR} ${BASH_SOURCE}:${LINENO}: Command failed with exit $errcode${RESET}" >&2' ERR
}
