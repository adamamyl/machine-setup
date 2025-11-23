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

# ----------------------------------------------------------------------
# Ensure an apt repository is added idempotently
# repo_name   - any short identifier (used for filename in sources.list.d)
# repo_line   - full "deb ..." line to add
# gpg_url     - optional, URL to key for signed-by
# ----------------------------------------------------------------------
ensure_apt_repo() {
  local repo_name="$1"
  local repo_line="$2"
  local gpg_url="${3:-}"

  local list_file="/etc/apt/sources.list.d/${repo_name}.list"
  local key_file="/etc/apt/keyrings/${repo_name}.gpg"

  # Create keyrings dir if GPG key is needed
  if [[ -n "$gpg_url" ]]; then
    _root_cmd "mkdir -p /etc/apt/keyrings"
    if [[ ! -f "$key_file" ]]; then
      info "Adding GPG key for $repo_name"
      _root_cmd "curl -fsSL $gpg_url | gpg --dearmor -o $key_file"
    else
      info "GPG key already exists for $repo_name"
    fi
  fi

  # Add repo line if missing
  if [[ ! -f "$list_file" || ! $(<"$list_file") == "$repo_line" ]]; then
    info "Adding apt repository $repo_name"
    _root_cmd "echo '$repo_line' > $list_file"
  else
    ok "Repository $repo_name already present"
  fi
}
