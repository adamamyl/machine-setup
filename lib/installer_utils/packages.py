import os
from .apt_tools import apt_install
from ..constants import STANDARD_PACKAGES, SYSTEM_REPOS, ROOT_SRC_CHECKOUT
from .git_tools import clone_or_update_repo

def install_packages(exec_obj: Executor) -> None:
    """Installs the list of standard packages."""
    log.info("Installing standard packages.")
    apt_install(exec_obj, STANDARD_PACKAGES)

def install_update_all_packages(exec_obj: Executor) -> None:
    """Wrapper to run the update-all-the-packages installer."""
    log.info("Ensuring 'update-all-the-packages' repository is installed and configured.")
    
    config = SYSTEM_REPOS.get("update-all-the-packages")
    if not config:
        log.error("Update package configuration missing from constants.")
        return

    repo_name = "update-all-the-packages"
    installer = config['installer']
    repo_url = config['url']
    dest_dir = os.path.join(ROOT_SRC_CHECKOUT, repo_name)

    clone_or_update_repo(exec_obj, repo_url, dest_dir)
    
    install_path = os.path.join(dest_dir, installer)
    if os.path.exists(install_path) and os.access(install_path, os.X_OK):
         exec_obj.run(f"pushd '{dest_dir}' >/dev/null && './{installer}' && popd >/dev/null", force_sudo=True)
    else:
        log.warning(f"Installer {install_path} missing or not executable, skipping.")