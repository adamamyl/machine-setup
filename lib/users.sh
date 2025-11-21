#!/usr/bin/env bash
set -euo pipefail

create_user() {
    local user="$1"
    if ! id "$user" >/dev/null 2>&1; then
        info "Creating user $user"
        useradd -m -s /bin/bash "$user"
    fi
}

add_user_to_group() {
    local user="$1"
    local group="$2"
    if ! id -nG "$user" | grep -qw "$group"; then
        info "Adding $user to $group"
        usermod -aG "$group" "$user"
    fi
}
