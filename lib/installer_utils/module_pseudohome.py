import os
import sys
import platform
from typing import List, Dict
from ..executor import Executor
from ..logger import log
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import set_homedir_perms_recursively, set_ssh_perms, clone_or_update_private_repo_with_key_check # MODIFIED IMPORT
from .repo_utils import _create_if_needed_ssh_key # Only need key creation/perms check here
from .tailscale import ensure_tailscale_connected # For issue 3 implementation

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

    # 2. SSH key setup (Idempotent check and generation + Permissions enforcement)
    ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
    
    # This function now guarantees the key exists and has strict permissions
    key_is_new = _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)
    
    # Ensure the .ssh directory itself has strict permissions before use
    set_ssh_perms(exec_obj, user, ssh_dir)
    
    # 3. Tailscale Connection Check (Prerequisite for git.amyl.org.uk)
    log.info("Checking Tailscale connection for git.amyl.org.uk access...")
    if not ensure_tailscale_connected(exec_obj):
        log.critical("❌ FATAL: Tailscale not connected. Cannot clone private git repo. Aborting setup.")
        return # Abort the rest of the function

    # 4. Clone/Update Repo (Handles interactive key prompt and retry on failure)
    ssh_key_path = os.path.join(ssh_dir, repo_name)
    
    clone_or_update_private_repo_with_key_check(
        exec_obj, 
        PSEUDOHOME_REPO_URL, 
        dest_dir, 
        ssh_key_path=ssh_key_path,
        repo_name=repo_name,
        extra_git_flags="--recursive", 
        user=user # Execute as 'adam'
    )
    
    # 5. Fix permissions
    exec_obj.run(f"chown -R {user}:{user} {os.path.dirname(dest_dir)}", force_sudo=True)
    set_homedir_perms_recursively(exec_obj, user, dest_dir)

    # 6. Run installer script (as the user)
    installer_path = os.path.join(dest_dir, PSEUDOHOME_INSTALLER)
    if os.path.exists(installer_path) and os.access(installer_path, os.X_OK):
        log.info("Running pseudohome installer script...")
        exec_obj.run(f"'{installer_path}'", user=user) 
    else:
        log.warning(f"Installer {PSEUDOHOME_INSTALLER} not executable, skipping.")
        
    log.success(f"Pseudohome setup complete for {user}.")