#!/usr/bin/env bash
set -euo pipefail
install_cloud_init_repo(){
    [[ -d /usr/local/src/post-cloud-init ]] && ok "post-cloud-init already installed" || git clone https://github.com/adamamyl/post-cloud-init /usr/local/src/post-cloud-init && /usr/local/src/post-cloud-init/install
}
