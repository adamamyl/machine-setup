import shutil
import platform
import os
from typing import List, Optional, Union, Dict
import subprocess

from ..executor import Executor
from ..logger import log
from ..constants import DOCKER_DEPS, DOCKER_PKGS
from .apt_tools import apt_install, ensure_apt_repo
from .user_mgmt import add_user_to_group

def _get_os_release() -> Dict[str, str]:
    """
    Parses /etc/os-release into a dictionary natively.
    Replaces brittle shell 'grep/cut/tr' with robust Python string matching.
    """
    info = {}
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.rstrip().split("=", 1)
                        # Remove surrounding quotes often found in these files
                        info[key] = value.strip('"')
    except Exception as e:
        log.error(f"Failed to read /etc/os-release: {e}")
    return info

def _remove_old_docker(exec_obj: Executor) -> None:
    """
    Removes old, conflicting, or manually installed Docker packages 
    using the comprehensive selection method.
    """
    log.info("Checking for and removing old/conflicting Docker packages...")
    
    # Comprehensive query command to find packages that need removal
    query_cmd = "dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1"
    
    try:
        # Execute the query command as root to get the list of packages to remove
        # run_quiet=True suppresses the execution logging here
        result = exec_obj.run(query_cmd, force_sudo=True, check=False, run_quiet=True)
        packages_to_remove = result.stdout.strip().split()
        
        if not packages_to_remove:
            log.success("No old Docker or conflicting packages found to remove.")
            return

        # 2. Construct the removal command
        remove_cmd = ["apt", "remove", "-y"] + packages_to_remove
        
        log.warning(f"Removing the following old/conflicting packages: {', '.join(packages_to_remove)}")
        
        # Execute the removal command
        # We allow check=False in case some packages are listed by dpkg but apt fails to find them, though unlikely here.
        exec_obj.run(remove_cmd, force_sudo=True, check=True)
        log.success("Old Docker packages successfully removed.")

    except Exception as e:
        log.warning(f"Failed to execute package removal query or removal. Continuing installation.")
        log.debug(f"Removal error: {e}")
        # We don't halt here, as the subsequent installation step will fail if necessary.

def install_docker_and_add_users(exec_obj: Executor, *users_to_add: str) -> None:
    """
    Installs Docker packages, starts the service, and adds users to the 'docker' group.
    Supports both Ubuntu and Debian automatically.
    """
    # Safeguard for macOS
    if platform.system().lower() == "darwin":
        log.warning("Docker Engine installation is not supported on macOS via this orchestrator.")
        return
    
    if shutil.which("docker"):
        log.success("Docker binary detected, skipping installation steps.")
        _verify_docker_installation(exec_obj)
        
    else:
        _remove_old_docker(exec_obj)
        
        log.info("Installing Docker from official repository...")
        
        # DOCKER_DEPS includes ca-certificates and lsb-release
        apt_install(exec_obj, DOCKER_DEPS)

        # 1. Detect OS details using Python dictionary matching
        os_info = _get_os_release()
        os_id = os_info.get("ID")  # e.g., 'ubuntu' or 'debian'
        codename = os_info.get("VERSION_CODENAME")  # e.g., 'noble' or 'bookworm'
        
        if not os_id or not codename:
            log.critical("Could not detect OS ID or Codename from /etc/os-release. Aborting Docker setup.")
            raise RuntimeError("Cannot proceed without distribution details.")

        log.info(f"Detected OS: {os_id}, Codename: {codename}")

        keyrings_dir = "/etc/apt/keyrings"
        docker_gpg_path = os.path.join(keyrings_dir, "docker.gpg") # Modern standard uses .gpg binary
        list_file = "/etc/apt/sources.list.d/docker.list"
        
        exec_obj.run(f"mkdir -p {keyrings_dir}", force_sudo=True)
        
        if not os.path.exists(docker_gpg_path):
            log.info(f"Downloading and adding Docker GPG key for {os_id}.")
            # Note: We use gpg --dearmor to ensure a binary .gpg file for /etc/apt/keyrings compatibility
            curl_cmd = f"curl -fsSL https://download.docker.com/linux/{os_id}/gpg | gpg --dearmor -o {docker_gpg_path}"
            exec_obj.run(curl_cmd, force_sudo=True)
            # Ensure proper read permissions for apt
            exec_obj.run(f"chmod a+r {docker_gpg_path}", force_sudo=True)
        else:
            log.info("Docker GPG key already exists.")

        arch = platform.machine()
        
        # --- FIX: Architecture Correction (aarch64 -> arm64) ---
        # If the detected arch is aarch64, use the APT standard 'arm64' for the repo line.
        if arch == 'aarch64':
            display_arch = 'arm64'
        else:
            display_arch = arch

        # 2. Interpolate the correct ID, codename and arch into the repository line
        repo_line = f"deb [arch={display_arch} signed-by={docker_gpg_path}] https://download.docker.com/linux/{os_id} {codename} stable"
        
        log.info(f"Using APT repository line: {repo_line}")
        ensure_apt_repo(exec_obj, list_file, repo_line)

        apt_install(exec_obj, DOCKER_PKGS)

        log.info("Enabling Docker service.")
        exec_obj.run("systemctl enable docker --now", force_sudo=True)
        
        _verify_docker_installation(exec_obj)


    exec_obj.run("groupadd -f docker", force_sudo=True)
    for user in users_to_add:
        add_user_to_group(exec_obj, user, "docker")
        log.success(f"Added {user} to docker group.")
    
    log.success("Docker installation complete.")

def _verify_docker_installation(exec_obj: Executor) -> None:
    """
    Runs a simple Docker command (like 'docker run hello-world') and cleans up the resulting image/container.
    """
    log.info("Running post-installation verification test...")
    
    # Use the simplest possible test: docker info
    try:
        exec_obj.run(["docker", "info"], check=True, force_sudo=True, run_quiet=True)
        log.success("Docker engine is running and responsive.")
    except Exception as e:
        log.critical("Docker verification failed. Docker service may not be running correctly.")
        log.debug(f"Docker info error: {e}")
        return

    # Use a basic container test that doesn't rely on remote registries
    try:
        log.info("Testing container execution with 'docker run hello-world'...")
        exec_obj.run(["docker", "run", "hello-world"], check=True, force_sudo=True)
        log.success("Container test completed successfully.")
    except Exception as e:
        log.warning("Container test failed. Connectivity or environment issue detected.")
        log.debug(f"Container test error: {e}")
    finally:
        # Cleanup: Remove the container and image to maintain a clean system state.
        log.info("Cleaning up test container and image...")
        
        # 1. Remove the last created container (the hello-world container)
        exec_obj.run("docker rm $(docker ps -lq) || true", force_sudo=True, run_quiet=True)
        # 2. Remove the hello-world image
        exec_obj.run("docker rmi hello-world || true", force_sudo=True, run_quiet=True)
        log.success("Test artifacts cleaned up.")


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