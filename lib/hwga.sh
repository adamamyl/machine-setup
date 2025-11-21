#!/usr/bin/env bash
set -euo pipefail

HWGA_DIR="/usr/local/src"
NO2ID_REPO="git@github.com:no2id/herewegoagain.git"
FAKE_LE_REPO="git@github.com:adamamyl/fake-le.git"

setup_hwga_no2id() {
    require_user no2id-docker
    add_user_to_group no2id-docker docker

    # Ensure /usr/local/src is group writable
    mkdir -p "$HWGA_DIR"
    chgrp docker "$HWGA_DIR"
    chmod g+ws "$HWGA_DIR"

    # === NO2ID deploy key ===
    local no2id_key="$HOME/.ssh/no2id-docker"
    if [[ ! -f "$no2id_key" ]]; then
        ssh-keygen -t ed25519 -f "$no2id_key" -N "" -C "no2id-docker@$(hostname)"
    fi
    info "Add this public key to: https://github.com/no2id/herewegoagain/settings/keys"
    cat "$no2id_key.pub"
    read -p "Press Enter once the key is added for NO2ID..."

    # Clone/update NO2ID repo
    local no2id_dest="$HWGA_DIR/herewegoagain"
    clone_or_update_repo "$NO2ID_REPO" "$no2id_dest" "$no2id_key"

    # === FAKE-LE deploy key ===
    local fake_key="$HOME/.ssh/fake-le-docker"
    if [[ ! -f "$fake_key" ]]; then
        ssh-keygen -t ed25519 -f "$fake_key" -N "" -C "fake-le-docker@$(hostname)"
    fi
    info "Add this public key to: https://github.com/adamamyl/fake-le/settings/keys"
    cat "$fake_key.pub"
    read -p "Press Enter once the key is added for FAKE-LE..."

    # Clone/update FAKE-LE repo
    local fake_dest="$HWGA_DIR/fake-le"
    clone_or_update_repo "$FAKE_LE_REPO" "$fake_dest" "$fake_key"

    # Run installer if exists
    if [[ -x "$fake_dest/fake-le-for-no2id-docker-installer" ]]; then
        "$fake_dest/fake-le-for-no2id-docker-installer"
    else
        warn "Fake-LE installer not executable, skipping"
    fi

    ok "HWGA / no2id setup complete"
}
