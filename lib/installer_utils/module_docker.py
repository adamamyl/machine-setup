import shutil
import platform
import os
import time
from typing import List, Dict
import subprocess

from ..executor import Executor
from ..logger import log
from ..constants import DOCKER_DEPS, DOCKER_PKGS, ROOTLESS_DOCKER_DEPS
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
    query_cmd = (
        "dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc "
        "podman-docker containerd runc | cut -f1"
    )
    
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
        
        log.warning(
            f"Removing the following old/conflicting packages: {', '.join(packages_to_remove)}"
        )
        
        # Execute the removal command
        # check=False: dpkg may list packages that apt can't find; we continue regardless.
        exec_obj.run(remove_cmd, force_sudo=True, check=True)
        log.success("Old Docker packages successfully removed.")

    except Exception as e:
        log.warning("Failed to execute package removal query or removal. Continuing installation.")
        log.debug(f"Removal error: {e}")
        # We don't halt here, as the subsequent installation step will fail if necessary.

def install_docker_and_add_users(
    exec_obj: Executor, *users_to_add: str, rootless: bool = True
) -> None:
    """
    Installs Docker packages (system-wide daemon) and Docker Compose plugin.
    Supports both Ubuntu and Debian automatically.

    By default each user in *users_to_add* gets their own rootless Docker
    daemon (per docs.docker.com/engine/security/rootless/) rather than being
    added to the 'docker' group, which is root-equivalent. The system-wide
    daemon is still installed/enabled regardless, since other modules
    (no2id-docker, ollama-docker) bind-mount /var/run/docker.sock and depend
    on it; rootless and rootful Docker coexist fine on the same host.

    Pass rootless=False to restore the old behaviour of adding users to the
    'docker' group instead.
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
        # Docker's Ubuntu install docs prefer UBUNTU_CODENAME over VERSION_CODENAME
        # (falling back to the latter): unofficial derivatives like Mint or Pop!_OS
        # report their own VERSION_CODENAME but still carry UBUNTU_CODENAME for the
        # underlying Ubuntu release Docker's repo actually publishes packages for.
        codename = os_info.get("UBUNTU_CODENAME") or os_info.get("VERSION_CODENAME")

        if not os_id or not codename:
            log.critical(
                "Could not detect OS ID or Codename from /etc/os-release. Aborting Docker setup."
            )
            raise RuntimeError("Cannot proceed without distribution details.")

        log.info(f"Detected OS: {os_id}, Codename: {codename}")

        # Docker's repo lags behind new Debian releases. Fall back to the last
        # known supported codename if the detected one isn't published yet.
        DEBIAN_DOCKER_FALLBACK = {
            "trixie": "bookworm",
            "forky": "trixie",  # Debian 14, future-proofing
        }
        if os_id == "debian" and codename in DEBIAN_DOCKER_FALLBACK:
            fallback = DEBIAN_DOCKER_FALLBACK[codename]
            log.warning(
                f"Docker repo has no packages for Debian '{codename}' yet. "
                f"Using '{fallback}' repo (compatible binaries)."
            )
            codename = fallback

        keyrings_dir = "/etc/apt/keyrings"
        docker_gpg_path = os.path.join(keyrings_dir, "docker.gpg")
        list_file = "/etc/apt/sources.list.d/docker.list"
        
        exec_obj.run(f"mkdir -p {keyrings_dir}", force_sudo=True)
        
        if not os.path.exists(docker_gpg_path):
            log.info(f"Downloading and adding Docker GPG key for {os_id}.")
            curl_cmd = (
                f"curl -fsSL https://download.docker.com/linux/{os_id}/gpg "
                f"| gpg --dearmor -o {docker_gpg_path}"
            )
            exec_obj.run(curl_cmd, force_sudo=True)
            # Ensure proper read permissions for apt
            exec_obj.run(f"chmod a+r {docker_gpg_path}", force_sudo=True)
        else:
            log.info("Docker GPG key already exists.")

        arch = platform.machine()
        
        ARCH_MAP = {"x86_64": "amd64", "aarch64": "arm64"}
        display_arch = ARCH_MAP.get(arch, arch)

        # 2. Interpolate the correct ID, codename and arch into the repository line
        repo_line = (
            f"deb [arch={display_arch} signed-by={docker_gpg_path}]"
            f" https://download.docker.com/linux/{os_id} {codename} stable"
        )
        
        log.info(f"Using APT repository line: {repo_line}")
        ensure_apt_repo(exec_obj, list_file, repo_line)

        apt_install(exec_obj, DOCKER_PKGS)

        log.info("Enabling Docker service.")
        exec_obj.run("systemctl enable docker --now", force_sudo=True)
        
        _verify_docker_installation(exec_obj)


    exec_obj.run("groupadd -f docker", force_sudo=True)

    if rootless:
        apt_install(exec_obj, ROOTLESS_DOCKER_DEPS)
        for user in users_to_add:
            _setup_rootless_docker(exec_obj, user)
    else:
        for user in users_to_add:
            add_user_to_group(exec_obj, user, "docker")
            log.success(f"Added {user} to docker group.")

    log.success("Docker installation complete.")


def _user_exists(user: str) -> bool:
    return subprocess.run(
        ['id', user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def _get_uid(user: str) -> int:
    return int(subprocess.run(
        ['id', '-u', user], capture_output=True, text=True, check=True
    ).stdout.strip())


def _get_homedir(user: str) -> str:
    result = subprocess.run(
        ['getent', 'passwd', user], capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split(':')[5]


def _ensure_subid_range(exec_obj: Executor, path: str, user: str) -> None:
    """
    Ensures /etc/subuid or /etc/subgid has a 65536-wide range for user.
    Modern useradd assigns this automatically; this is a fallback for
    accounts created before that became the default, matching the
    guidance in Docker's get.docker.com/rootless install script.
    """
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []

    if any(line.startswith(f"{user}:") for line in lines):
        log.info(f"{path} already has a range for '{user}'.")
        return

    # Pick a start beyond any existing range so we don't collide with one.
    starts_and_sizes = []
    for line in lines:
        parts = line.split(':')
        if len(parts) == 3:
            try:
                starts_and_sizes.append((int(parts[1]), int(parts[2])))
            except ValueError:
                continue
    next_start = max((start + size for start, size in starts_and_sizes), default=100000)
    next_start = max(next_start, 100000)

    log.info(f"Adding subordinate ID range {next_start}:65536 for '{user}' in {path}.")
    exec_obj.run(f"echo '{user}:{next_start}:65536' | tee -a {path} > /dev/null", force_sudo=True)


def _setup_rootless_docker(exec_obj: Executor, user: str) -> None:
    """
    Configures rootless Docker for *user*: uidmap prerequisites, subuid/subgid
    ranges, lingering (so their systemd --user instance survives without an
    active login), then runs dockerd-rootless-setuptool.sh as that user.

    --force is passed to the setuptool because the system-wide dockerd is
    intentionally left running for other services; rootless and rootful
    Docker run side by side using separate sockets.
    """
    if not _user_exists(user):
        log.warning(f"User '{user}' does not exist; skipping rootless Docker setup.")
        return

    _ensure_subid_range(exec_obj, "/etc/subuid", user)
    _ensure_subid_range(exec_obj, "/etc/subgid", user)

    log.info(f"Enabling lingering for '{user}' so their user services survive logout/boot.")
    exec_obj.run(f"loginctl enable-linger {user}", force_sudo=True)

    uid = _get_uid(user)
    runtime_dir = f"/run/user/{uid}"

    # Lingering triggers systemd-logind to create the runtime dir; give it a
    # moment to appear rather than sleeping blindly.
    for _ in range(10):
        if os.path.isdir(runtime_dir) or exec_obj.dry_run:
            break
        time.sleep(1)
    else:
        log.warning(f"{runtime_dir} did not appear after enabling linger; proceeding anyway.")

    env_prefix = f"XDG_RUNTIME_DIR={runtime_dir} PATH=/usr/bin:$PATH"

    log.info(f"Running dockerd-rootless-setuptool.sh for '{user}'...")
    exec_obj.run(
        f"{env_prefix} dockerd-rootless-setuptool.sh install --force",
        user=user,
        check=True,
    )

    log.info(f"Enabling and starting the rootless docker.service for '{user}'...")
    exec_obj.run(
        f"XDG_RUNTIME_DIR={runtime_dir} systemctl --user enable --now docker.service",
        user=user,
        check=True,
    )

    _add_rootless_env_to_shell_rc(exec_obj, user, uid)
    _verify_rootless_docker(exec_obj, user, runtime_dir)


def _add_rootless_env_to_shell_rc(exec_obj: Executor, user: str, uid: int) -> None:
    """Adds the DOCKER_HOST export Docker's docs recommend to the user's ~/.bashrc (idempotent)."""
    marker = "# Added by machine-setup: rootless Docker"
    export_line = f'export DOCKER_HOST="unix:///run/user/{uid}/docker.sock"'

    try:
        bashrc = os.path.join(_get_homedir(user), ".bashrc")
    except subprocess.CalledProcessError:
        log.warning(f"Could not determine homedir for '{user}'; skipping .bashrc update.")
        return

    existing = ""
    if os.path.exists(bashrc):
        with open(bashrc) as f:
            existing = f.read()

    if marker in existing:
        log.info(f"{bashrc} already configured for rootless Docker.")
        return

    log.info(f"Adding DOCKER_HOST export to {bashrc} for '{user}'.")
    block = f"\n{marker}\n{export_line}\n"
    exec_obj.run(f"printf '%s' '{block}' | tee -a {bashrc} > /dev/null", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {bashrc}", force_sudo=True)


def _verify_rootless_docker(exec_obj: Executor, user: str, runtime_dir: str) -> None:
    """Runs 'docker info' as user against their rootless socket to confirm it's up."""
    try:
        result = exec_obj.run(
            f"XDG_RUNTIME_DIR={runtime_dir} docker info",
            user=user,
            check=True,
            run_quiet=True,
        )
        if "rootless" in result.stdout.lower():
            log.success(f"Rootless Docker is running for '{user}'.")
        else:
            log.warning(
                f"'docker info' succeeded for '{user}' but doesn't report rootless mode."
            )
    except subprocess.CalledProcessError as e:
        log.warning(f"Could not verify rootless Docker for '{user}'.")
        log.debug(f"docker info error: {e}")

def _verify_docker_installation(exec_obj: Executor) -> None:
    """
    Runs 'docker info' and 'docker run hello-world' to verify installation, then cleans up.
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
        result = exec_obj.run(
            ["docker", "volume", "ls", "-q", "-f", f"name=^{volume_name}$"],
            check=True,
            force_sudo=True,
            run_quiet=True,
        )
        if result.stdout.strip() == volume_name:
            log.success(f"Docker volume '{volume_name}' exists.")
            return True
        log.warning(f"Docker volume '{volume_name}' not found.")
        return False
    except subprocess.CalledProcessError as e:
        log.error(f"Error checking Docker volumes: {e.stderr}")
        return False

def are_docker_services_running(
    exec_obj: Executor, user: str, cwd: str, service_names: List[str]
) -> bool:
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
        log.warning("Failed to execute 'docker compose ps'. Stack may not exist.")
        log.debug(f"PS error: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error during Docker Compose status check: {e}")
        return False