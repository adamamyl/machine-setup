#!/usr/bin/env bash
set -euo pipefail

create_user() {
    local u="$1"
    id "$u" >/dev/null 2>&1 || useradd -m -s /bin/bash "$u"
    }

add_user_to_group() {
    local u="$1" g="$2"
    id -nG "$u" | grep -qw "$g" || usermod -aG "$g" "$u"
    }