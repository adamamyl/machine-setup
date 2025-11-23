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
      apt update -y -qq
    else
      apt update -y
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
          apt install -y -qq "$pkg"
        else
          apt install -y "$pkg"
        fi
      fi
    fi
  done
}

apt_autoremove() {
  if [[ "${DRY_RUN:-}" ]]; then
    info "[DRY-RUN] apt autoremove -y" "$QUIET"
  else
    if [[ "$QUIET" == true ]]; then
      apt autoremove -y -qq
    else
      apt autoremove -y
    fi
  fi
}
