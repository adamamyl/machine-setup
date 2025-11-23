#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

source "$LIB_DIR/helpers-extra/apt-behaviour.sh"

install_packages() {
  info "Installing standard packages"
  local pkgs=(diceware findutils grep gzip hostname iputils-ping net-tools openssh-server vim python3 git curl mtr tree)
  apt_install "${pkgs[@]}"
}
