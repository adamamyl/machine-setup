import subprocess
from typing import List
from ..executor import Executor
from ..logger import log

def _is_package_installed(pkg: str) -> bool:
    """Checks if a package is installed using dpkg -s."""
    try:
        # Use subprocess.run directly as we don't need Executor for a simple check
        subprocess.run(['dpkg', '-s', pkg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def apt_install(exec_obj: Executor, packages: List[str]) -> None:
    """Installs a list of packages in a single command after checking for existing installations."""
    if not packages:
        log.warning("No packages specified for installation")
        return

    missing_packages: List[str] = []
    already_installed_count = 0

    # 1. Determine which packages are missing
    for pkg in packages:
        if _is_package_installed(pkg):
            log.info(f"{pkg} already installed (skipped)")
            already_installed_count += 1
        else:
            missing_packages.append(pkg)

    if not missing_packages:
        log.success(f"All packages ({already_installed_count}) were already installed.")
        return

    # 2. Update apt cache
    log.info("Updating APT cache...")
    # Use -qq for quiet update
    exec_obj.run("apt update -y -qq", force_sudo=True)
    
    # 3. Install all missing packages in one go
    packages_to_install_str = " ".join(missing_packages)
    
    log.info(f"Installing {len(missing_packages)} package(s): {packages_to_install_str}")
    
    install_cmd = f"apt install -y {packages_to_install_str}"
    
    if exec_obj.quiet:
        install_cmd += " -qq"
    
    exec_obj.run(install_cmd, force_sudo=True)
    
    log.success(f"Successfully installed packages: {packages_to_install_str}")

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