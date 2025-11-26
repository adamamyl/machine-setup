import shutil
import platform
import os
from typing import List
from ..executor import Executor
from ..logger import log
from ..constants import DOCKER_DEPS, DOCKER_PKGS
from .apt_tools import apt_install, ensure_apt_repo
from .user_mgmt import add_user_to_group

OLD_DOCKER_PKGS: List[str] = [
    "docker", "docker-engine", "docker.io", "containerd", "runc"
]

def _remove_old_docker(exec_obj: Executor) -> None:
    """Removes old or conflicting Docker packages."""
    log.info("Checking for and removing old/conflicting Docker packages...")
    
    cmd = f"apt purge -y {' '.join(OLD_DOCKER_PKGS)} || true"
    exec_obj.run(cmd, force_sudo=True)
    

def install_docker_and_add_users(exec_obj: Executor, *users_to_add: str) -> None:
    """Installs Docker packages, starts the service, and adds users to the 'docker' group."""
    
    if shutil.which("docker"):
        log.success("Docker binary detected, skipping installation steps.")
    else:
        _remove_old_docker(exec_obj)
        
        log.info("Installing Docker from official repository...")
        
        apt_install(exec_obj, DOCKER_DEPS)

        keyrings_dir = "/etc/apt/keyrings"
        docker_gpg_path = os.path.join(keyrings_dir, "docker.gpg")
        list_file = "/etc/apt/sources.list.d/docker.list"
        
        exec_obj.run(f"mkdir -p {keyrings_dir}", force_sudo=True)
        
        if not os.path.exists(docker_gpg_path):
            log.info("Downloading and adding Docker GPG key.")
            curl_cmd = f"curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o {docker_gpg_path}"
            exec_obj.run(curl_cmd, force_sudo=True)
        else:
            log.info("Docker GPG key already exists.")

        arch = platform.machine()
        repo_line = f"deb [arch={arch} signed-by={docker_gpg_path}] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        ensure_apt_repo(exec_obj, list_file, repo_line)

        apt_install(exec_obj, DOCKER_PKGS)

        log.info("Enabling Docker service.")
        exec_obj.run("systemctl enable docker --now", force_sudo=True)

    exec_obj.run("groupadd -f docker", force_sudo=True)
    for user in users_to_add:
        add_user_to_group(exec_obj, user, "docker")
        log.success(f"Added {user} to docker group.")
    
    log.success("Docker installation complete.")