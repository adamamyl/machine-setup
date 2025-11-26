import os
import sys
import platform
from typing import List, Dict
from ..executor import Executor
from ..logger import log
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import clone_or_update_repo, set_homedir_perms_recursively, set_ssh_perms
from .module_no2id import _display_key_and_url_for_repo, _create_if_needed_ssh_key

PSEUDOHOME_USER: str = "adam"
PSEUDOHOME_REPO_NAME: str = "pseudohome"
PSEUDOHOME_REPO_URL: str = "adam@git.amyl.org.uk:/data/git/pseudoadam"
PSEUDOHOME_DEST_DIR: str = os.path.join(os.path.expanduser(f"~{PSEUDOHOME_USER}"), PSEUDOHOME_REPO_NAME)
PSEUDOHOME_INSTALLER: str = "pseudohome-symlinks"


def setup_pseudohome(exec_obj: Executor, venv_dir: str) -> None:
    """Setup 'adam' user, groups, SSH key, clone/update pseudohome."""
    log.info("Starting Pseudohome setup for 'adam'...")

    user = PSEUDOHOME_USER
    repo_name = PSEUDOHOME_REPO_NAME
    dest_dir = PSEUDOHOME_DEST_DIR
    
    users_to_groups_if_needed(exec_obj, user, ["docker", "staff"])

    ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
    _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)
    
    _display_key_and_url_for_repo(ssh_dir, repo_name, PSEUDOHOME_REPO_URL)
    
    ssh_key_path = os.path.join(ssh_dir, repo_name)
    clone_or_update_repo(exec_obj, PSEUDOHOME_REPO_URL, dest_dir, ssh_key_path, "--recursive")
    
    # Ensure owner:group is adam:adam for the destination directory's parent (typically /home/adam)
    exec_obj.run(f"chown -R {user}:{user} {os.path.dirname(dest_dir)}", force_sudo=True)
    set_homedir_perms_recursively(exec_obj, user, dest_dir)
    set_ssh_perms(exec_obj, user, ssh_dir)

    install_path = os.path.join(dest_dir, PSEUDOHOME_INSTALLER)
    if os.path.exists(install_path) and os.access(install_path, os.X_OK):
        log.info("Running pseudohome installer script...")
        env_vars = {
            "VENVDIR": venv_dir,
            "PATH": f"{venv_dir}/bin:{os.environ.get('PATH', '')}"
        }
        exec_obj.run(f"'{install_path}'", user=user, env=env_vars)
    else:
        log.warning(f"Installer {PSEUDOHOME_INSTALLER} not executable, skipping.")
        
    log.success(f"Pseudohome setup complete for {user}.")