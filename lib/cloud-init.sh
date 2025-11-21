#!/usr/bin/env bash
set -euo pipefail

install_cloud_init_repo(){
    info "Installing post-cloud-init"
    git clone https://github.com/adamamyl/post-cloud-init /usr/src/post-cloud-init
    /usr/src/post-cloud-init/install
}
