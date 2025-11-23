#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ----------------------------------------------------------------------
# Centralized apt helper respecting DRY_RUN and QUIET
# ----------------------------------------------------------------------
apt_install() {
  local packages=("$@")
  if [[ "${#packages[@]}" -eq 0 ]]; then
    warn "No packages specified for installation" "$QUIET"
    return 0
  fi

  # Update apt cache
  if [[ "${DRY_RUN:-}" == true ]]; then
    info "[DRY-RUN] apt update" "$QUIET"
  else
    if [[ "$QUIET" == true ]]; then
      _root_cmd "apt update -y -qq"
    else
      _root_cmd "apt update -y"
    fi
  fi

  # Install each package
  for pkg in "${packages[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      ok "$pkg already installed" "$QUIET"
    else
      if [[ "${DRY_RUN:-}" == true ]]; then
        info "[DRY-RUN] apt install -y $pkg" "$QUIET"
      else
        info "Installing $pkg..." "$QUIET"
        if [[ "$QUIET" == true ]]; then
          _root_cmd "apt install -y -qq $pkg"
        else
          _root_cmd "apt install -y $pkg"
        fi
      fi
    fi
  done
}

apt_autoremove() {
  if [[ "${DRY_RUN:-}" == true ]]; then
    info "[DRY-RUN] apt autoremove -y" "$QUIET"
  else
    if [[ "$QUIET" == true ]]; then
      _root_cmd "apt autoremove -y -qq"
    else
      _root_cmd "apt autoremove -y"
    fi
  fi
}

# ----------------------------------------------------------------------
# Add/ensure apt repository, idempotent, safe for multiple runs
# ----------------------------------------------------------------------
ensure_apt_repo() {
  local list_file="$1"
  local repo_line="$2"

  if [[ ! -f "$list_file" ]] || ! grep -Fxq "$repo_line" "$list_file"; then
    info "Adding apt repository: $list_file"
    echo "$repo_line" | _root_cmd "tee '$list_file' >/dev/null"
    _root_cmd "apt update -qq"
  else
    ok "Apt repository already present in $list_file" "$QUIET"
  fi
}
