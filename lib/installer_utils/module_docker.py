import shutil
import platform
import os
from typing import List
import subprocess
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

def run_docker_compose(exec_obj: Executor, user: str, cwd: str, command: str) -> None:
    """
    Executes a docker compose command in a specific directory as the specified user, 
    favoring the modern 'docker compose' syntax.
    """
    if not shutil.which("docker"):
        log.error("Docker not installed. Cannot run docker compose.")
        raise FileNotFoundError("Docker executable not found.")
        
    log.info(f"Executing Docker Compose command '{command}' in {cwd} as user '{user}'...")
    
    # 1. Prioritize the modern 'docker compose' syntax.
    compose_path = shutil.which("docker")
    if compose_path:
        # Use 'docker compose' syntax
        cmd_list = [compose_path, 'compose'] + command.split()
        log.debug(f"Using modern docker compose syntax: {cmd_list}")
    else:
        # 2. Fallback to legacy 'docker-compose' binary path.
        legacy_path = shutil.which("docker-compose")
        if legacy_path:
            cmd_list = [legacy_path] + command.split()
            log.warning("Falling back to legacy 'docker-compose' binary.")
        else:
            log.error("Neither 'docker compose' nor 'docker-compose' binary found.")
            raise FileNotFoundError("Docker Compose functionality missing.")

    # NOTE: user=user, check=True
    exec_obj.run(cmd_list, user=user, cwd=cwd, check=True)
    log.success(f"Docker Compose command '{command}' completed for {user} in {cwd}.")
    
def check_docker_volume_exists(exec_obj: Executor, volume_name: str) -> bool:
    """Checks if a named Docker volume exists."""
    log.info(f"Checking for existence of Docker volume: {volume_name}")
    try:
        # Use 'docker volume ls -q -f name=...' to check existence silently
        result = exec_obj.run(["docker", "volume", "ls", "-q", "-f", f"name=^{volume_name}$"], check=True, force_sudo=True, run_quiet=True)
        if result.stdout.strip() == volume_name:
            log.success(f"Docker volume '{volume_name}' exists.")
            return True
        log.warning(f"Docker volume '{volume_name}' not found.")
        return False
    except subprocess.CalledProcessError as e:
        log.error(f"Error checking Docker volumes: {e.stderr}")
        return False

def are_docker_services_running(exec_obj: Executor, user: str, cwd: str, service_names: List[str]) -> bool:
    """
    Checks if a list of specific Docker Compose services are currently in the 'running' state.
    Requires running as the user that owns the compose stack.
    """
    log.info(f"Checking status for services: {', '.join(service_names)} in {cwd}...")
    
    try:
        # We assume the modern 'docker compose' syntax is available
        compose_path = shutil.which("docker") 
        if not compose_path:
            log.error("Docker executable not found for status check.")
            return False

        # Run command: docker compose ps -a --format "{{.Service}} {{.State}}"
        cmd_list = [compose_path, 'compose', 'ps', '-a', '--format', '{{.Service}} {{.State}}']
        
        result = exec_obj.run(cmd_list, user=user, cwd=cwd, check=True, run_quiet=True)
        
        ps_output = result.stdout.lower()
        
        all_running = True
        
        for service in service_names:
            # Check for the pattern: "service_name running"
            if f"{service} running" not in ps_output:
                log.warning(f"Service '{service}' is NOT running or was not found.")
                all_running = False
                break
            
        return all_running
        
    except subprocess.CalledProcessError as e:
        log.warning(f"Failed to execute 'docker compose ps'. Stack may not exist.")
        log.debug(f"PS error: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error during Docker Compose status check: {e}")
        return False