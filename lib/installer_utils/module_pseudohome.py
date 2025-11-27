import os
import sys
import platform
from typing import List, Dict
from ..executor import Executor
from ..logger import log
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import clone_or_update_repo, set_homedir_perms_recursively, set_ssh_perms
from .repo_utils import _display_key_and_url_for_repo, _create_if_needed_ssh_key # NEW IMPORT LOCATION

# Constants
PSEUDOHOME_USER: str = "adam"
PSEUDOHOME_REPO_NAME: str = "pseudohome"
PSEUDOHOME_REPO_URL: str = "adam@git.amyl.org.uk:/data/git/pseudoadam"
PSEUDOHOME_DEST_DIR: str = os.path.join(f"/home/{PSEUDOHOME_USER}", PSEUDOHOME_REPO_NAME)
PSEUDOHOME_INSTALLER: str = "pseudohome-symlinks"


def setup_pseudohome(exec_obj: Executor) -> None:
    """
    Setup 'adam' user, groups, SSH key, clone/update pseudohome.
    Runs as root but executes user-specific commands as 'adam'.
    """
    log.info("Starting Pseudohome setup for 'adam'...")

    user = PSEUDOHOME_USER
    repo_name = PSEUDOHOME_REPO_NAME
    dest_dir = PSEUDOHOME_DEST_DIR
    
    # 1. User/Group setup
    users_to_groups_if_needed(exec_obj, user, ["docker", "staff"])

    # 2. SSH key setup
    ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
    
    # Capture if the key was NEWLY created (True/False)
    key_is_new = _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)
    
    # 3. Interactive Deploy Key Step
    if key_is_new: # <-- ONLY DISPLAY AND WAIT IF THE KEY IS NEW
        _display_key_and_url_for_repo(
            exec_obj, 
            ssh_dir,  
            repo_name, 
            PSEUDOHOME_REPO_URL 
        )
    else:
        log.info("Skipping interactive deploy key setup (Key already existed).")
    
    # 4. Clone/Update Repo
    ssh_key_path = os.path.join(ssh_dir, repo_name)
    clone_or_update_repo(
        exec_obj, 
        PSEUDOHOME_REPO_URL, 
        dest_dir, 
        ssh_key_path=ssh_key_path,
        extra_git_flags="--recursive", 
        user=user # Execute as 'adam'
    )
    
    # 5. Fix permissions
    exec_obj.run(f"chown -R {user}:{user} {os.path.dirname(dest_dir)}", force_sudo=True)
    set_homedir_perms_recursively(exec_obj, user, dest_dir)
    set_ssh_perms(exec_obj, user, ssh_dir)

    # 6. Run installer script (as the user)
    installer_path = os.path.join(dest_dir, PSEUDOHOME_INSTALLER)
    if os.path.exists(installer_path) and os.access(installer_path, os.X_OK):
        log.info("Running pseudohome installer script...")
        exec_obj.run(f"'{installer_path}'", user=user) 
    else:
        log.warning(f"Installer {PSEUDOHOME_INSTALLER} not executable, skipping.")
        
    log.success(f"Pseudohome setup complete for {user}.")