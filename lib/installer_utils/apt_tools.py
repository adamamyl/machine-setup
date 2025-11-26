import subprocess
from typing import List, Optional
from ..executor import Executor
from ..logger import log

def _is_package_installed(pkg: str) -> bool:
    """Checks if a package is installed using dpkg -s."""
    try:
        subprocess.run(['dpkg', '-s', pkg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def apt_install(exec_obj: Executor, packages: List[str]) -> None:
    """Installs a list of packages, checking first if they are already installed."""
    if not packages:
        log.warning("No packages specified for installation.")
        return

    log.info("Updating APT cache...")
    exec_obj.run("apt update -y -qq", force_sudo=True)

    for pkg in packages:
        if _is_package_installed(pkg):
            log.success(f"{pkg} already installed")
        else:
            log.info(f"Installing {pkg}...")
            install_cmd = f"apt install -y {pkg}"
            if exec_obj.quiet:
                install_cmd += " -qq"
            exec_obj.run(install_cmd, force_sudo=True)

def apt_autoremove(exec_obj: Executor) -> None:
    """Runs apt autoremove."""
    log.info("Running apt autoremove...")
    autoremove_cmd = "apt autoremove -y"
    if exec_obj.quiet:
        autoremove_cmd += " -qq"
    exec_obj.run(autoremove_cmd, force_sudo=True)

def ensure_apt_repo(exec_obj: Executor, list_file: str, repo_line: str) -> None:
    """Adds an apt repository line to a file if it is not already present, and deduplicates the file."""

    existing_lines = []
    try:
        with open(list_file, 'r') as f:
            existing_lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        pass

    if repo_line in existing_lines:
        log.success(f"APT repository already present in {list_file}")
        return

    all_lines = existing_lines + [repo_line]
    
    # Deduplicate while preserving order (using dict keys)
    unique_lines = list(dict.fromkeys(all_lines))
    content = "\n".join(unique_lines) + "\n"
    
    log.info(f"Adding/Deduplicating APT repository in: {list_file}")

    # Use tee to write the content with privilege
    cmd = f"echo \"{content}\" | tee \"{list_file}\" > /dev/null"
    exec_obj.run(cmd, force_sudo=True)
    
    exec_obj.run("apt update -qq", force_sudo=True)