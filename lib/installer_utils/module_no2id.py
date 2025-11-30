import os
import sys
import platform
from typing import List, Dict, Optional
from ..executor import Executor
from ..logger import log
from ..constants import HWGA_REPOS, ROOT_SRC_CHECKOUT, SYSTEM_REPOS
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import set_homedir_perms_recursively, set_ssh_perms, clone_or_update_private_repo_with_key_check
from .repo_utils import _create_if_needed_ssh_key, _dotenv_sync_if_needed


def setup_no2id(exec_obj: Executor) -> None:
    """
    Setup no2id-docker user, groups, SSH keys, and clone/update the NO2ID repos.
    Runs as root but executes user-specific Git commands as the target user.
    """
    log.info("Starting **NO2ID** setup...")
    
    # 1. Ensure base source dir exists
    exec_obj.run(f"mkdir -p {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chgrp docker {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chmod g+w {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chmod -s {ROOT_SRC_CHECKOUT}", force_sudo=True)

    for repo_name, config in HWGA_REPOS.items():
        user = config['user']
        dest_dir = config['dest']
        repo_url = config['url']
        installer = config['installer']
        extra_flags = config.get('extra_flags', "")
        
        log.info(f"Processing repository: {repo_name} for user: {user}")

        # 1. User/Group setup (Idempotent)
        groups = ["docker"]
        if user == "adam":
            groups.append("staff")
        users_to_groups_if_needed(exec_obj, user, groups)

        # 2. SSH key setup (Idempotent check and generation + Permissions enforcement)
        ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
        
        # This function now guarantees the key exists and has strict permissions
        key_is_new = _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)
        
        # Ensure the .ssh directory itself has strict permissions before use
        set_ssh_perms(exec_obj, user, ssh_dir)
        
        # 3. Clone/Update Repo (Handles interactive key prompt and retry on failure)
        ssh_key_path = os.path.join(ssh_dir, repo_name)
        
        clone_or_update_private_repo_with_key_check(
            exec_obj, 
            repo_url, 
            dest_dir, 
            ssh_key_path=ssh_key_path,
            repo_name=repo_name,
            extra_git_flags=extra_flags,
            user=user # Execute as target user
        )
        
        # 4. Fix permissions
        set_homedir_perms_recursively(exec_obj, user, dest_dir)
        
        # --- NEW STEP: Generate .env file if flagged in constants ---
        _dotenv_sync_if_needed(exec_obj, repo_name, user, dest_dir)

        # 5. Run installer script (as the user)
        installer_path = os.path.join(dest_dir, installer)
        
        # --- LOGIC: Skip installer requiring arguments ---
        if repo_name == "fake-le" and installer == "fake-le-for-no2id-docker-installer":
            log.info(f"Skipping installer {installer} for {repo_name}. This is now handled by the --fake-le module.")
            continue # Skip execution for this specific module
        
        # Execute all other installers
        if os.path.exists(installer_path) and os.access(installer_path, os.X_OK):
            log.info(f"Running installer {installer} for {repo_name} as user {user}...")
            exec_obj.run(f"'{installer_path}'", user=user) 
        elif installer:
            log.warning(f"Installer {installer} for {repo_name} not executable, skipping.")

    log.success("NO2ID setup complete.")


def install_system_repos(exec_obj: Executor) -> None:
    """Installs and runs installers for system-level GitHub repos (from SYSTEM_REPOS)."""
    log.info("Starting installation of system-level repositories...")

    base_dir = ROOT_SRC_CHECKOUT
    # Ensure base source dir exists and has correct permissions
    exec_obj.run(f"mkdir -p {base_dir}", force_sudo=True)
    exec_obj.run(f"chgrp docker {base_dir} || true", force_sudo=True)
    exec_obj.run(f"chmod g+w {base_dir}", force_sudo=True)
    exec_obj.run(f"chmod -s {base_dir}", force_sudo=True)

    for repo_name, config in SYSTEM_REPOS.items():
        installer = config['installer']
        repo_url = config['url']
        dest_dir = os.path.join(base_dir, repo_name)

        # Note: These are public/system repos, user=None (runs as root), so use low-level clone
        from .git_tools import clone_or_update_repo # Use low-level clone
        clone_or_update_repo(exec_obj, repo_url, dest_dir)

        # Fix permissions (root ownership)
        exec_obj.run(f"chown -R root:root {dest_dir}", force_sudo=True)
        exec_obj.run(f"chmod -R g+w {dest_dir}", force_sudo=True)
        exec_obj.run(f"chmod -s {dest_dir}", force_sudo=True)

        install_path = os.path.join(dest_dir, installer)
        if os.path.exists(install_path) and os.access(install_path, os.X_OK):
            log.info(f"Running {installer} for {repo_name}...")
            # Run inside the repo directory (as root)
            exec_obj.run(f"pushd '{dest_dir}' >/dev/null && './{installer}' && popd >/dev/null", force_sudo=True)
            log.success(f"Installer completed for {repo_name}.")
        else:
            log.warning(f"Installer {install_path} missing or not executable, skipping.")
            
    log.success("System repository installation finished.")