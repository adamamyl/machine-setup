#!/usr/bin/env bash
set -euo pipefail

is_linux(){ [[ "$(uname -s)" == "Linux" ]]; }
is_macos(){ [[ "$(uname -s)" == "Darwin" ]]; }
is_ubuntu_desktop(){ command -v lsb_release >/dev/null 2>&1 && lsb_release -si | grep -iq Ubuntu && [[ -n "$DISPLAY" ]]; }
is_gnome_desktop(){ is_ubuntu_desktop && [[ "$XDG_CURRENT_DESKTOP" == *GNOME* ]]; }
