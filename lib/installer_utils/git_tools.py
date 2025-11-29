import os
import subprocess
from typing import Optional, List
from ..executor import Executor
from ..logger import log
from ..constants import GIT_BIN_PATH # Import the dynamically resolved path
from .repo_utils import _display_key_and_url_for_repo # Import the interactive prompt utility
import time # For retry sleep

def clone_or_update_repo(exec_obj: Executor, 
                         repo_url: str, 
                         dest_dir: str, 
                         ssh_key_path: Optional[str] = None, 
                         extra_git_flags: Optional[str] = "",
                         user: Optional[str] = None) -> None:
    """
    Clones or updates a Git repository, handling SSH deploy keys if specified.
    
    NOTE: This is the low-level function that performs the actual shell execution.
    For private repos that require interactive key setup/retry, use 
    clone_or_update_private_repo_with_key_check().
    
    :param exec_obj: The Executor instance.
    :param repo_url: URL of the repository.
    :param dest_dir: Local path to clone into.
    :param ssh_key_path: Path to the private SSH key file (used to set GIT_SSH_COMMAND).
    :param extra_git_flags: Additional flags for the clone command (e.g., '--recursive').
    :param user: The system user to run the git commands as (required for SSH access).
    :raises: subprocess.CalledProcessError
    """
    
    parent_dir = os.path.dirname(dest_dir)
    
    # 1. Ensure parent dir exists and has correct group/permissions
    exec_obj.run(f"mkdir -p {parent_dir}", force_sudo=True)
    
    # Use 'docker' group and ensure recursive chmod
    exec_obj.run(f"chgrp -R docker {parent_dir} || true", force_sudo=True)
    exec_obj.run(f"chmod -R g+w {parent_dir}", force_sudo=True)
    exec_obj.run(f"chmod -R -s {parent_dir} || true", force_sudo=True)

    # 2. Prepare environment prefix for SSH key usage
    env_prefix = "" 
    if ssh_key_path:
        # Define the SSH command using the deploy key.
        # FIX: Use double quotes for the path to prevent premature string termination in bash -c
        ssh_command = f"ssh -i \"{ssh_key_path}\" -o IdentitiesOnly=yes"
        # Bundle the environment setting command string directly into the prefix
        env_prefix = f"GIT_SSH_COMMAND='{ssh_command}' "
        log.debug(f"Using GIT_SSH_COMMAND prefix: {env_prefix}")
    
    # 3. Check if repo exists and handle update/integrity
    if os.path.isdir(os.path.join(dest_dir, ".git")):
        try:
            # INTEGRITY CHECK: Use the resolved path constant (GIT_BIN_PATH)
            exec_obj.run([GIT_BIN_PATH, '-C', dest_dir, 'rev-parse', '--is-inside-work-tree'], user=user) 
            
            log.info(f"Updating existing repository: {dest_dir}")
            
            # FETCH: Prepend the env_prefix to the command string
            fetch_cmd = f"{env_prefix} {GIT_BIN_PATH} -C '{dest_dir}' fetch --all --prune"
            exec_obj.run(fetch_cmd, user=user)
            log.success(f"Repository updated: {dest_dir}")
            
        except Exception:
            # Integrity check or fetch failed -> Remove and re-clone
            log.warning(f"Repo integrity check or fetch failed at {dest_dir}; removing and recloning.")
            exec_obj.run(f"rm -rf {dest_dir}", force_sudo=True)
        
    # 4. Clone if missing or just removed
    if not os.path.isdir(os.path.join(dest_dir, ".git")):
        log.info(f"Cloning {repo_url} -> {dest_dir}")
        
        # Assemble the raw clone command string
        clone_options = ""
        if extra_git_flags:
            clone_options = extra_git_flags
        
        # FINAL COMMAND STRING: GIT_SSH_COMMAND='...' /path/to/git clone ...
        final_cmd = f"{env_prefix} {GIT_BIN_PATH} clone {clone_options} '{repo_url}' '{dest_dir}'"
        
        exec_obj.run(final_cmd, user=user)
        log.success(f"Repository cloned: {dest_dir}")

def clone_or_update_private_repo_with_key_check(exec_obj: Executor, 
                                               repo_url: str, 
                                               dest_dir: str, 
                                               ssh_key_path: str, 
                                               repo_name: str,
                                               extra_git_flags: Optional[str] = "",
                                               user: str = "root") -> None:
    """
    Attempts to clone a private repo. If it fails due to SSH permission,
    it prompts the user to add the deploy key and retries the clone once.
    """
    
    MAX_CLONE_ATTEMPTS = 2 
    clone_succeeded = False
    
    for attempt in range(MAX_CLONE_ATTEMPTS):
        try:
            log.info(f"Attempting to clone/update repository (Attempt {attempt + 1}/{MAX_CLONE_ATTEMPTS})...")
            clone_or_update_repo(
                exec_obj, 
                repo_url, 
                dest_dir, 
                ssh_key_path=ssh_key_path,
                extra_git_flags=extra_git_flags,
                user=user
            )
            clone_succeeded = True
            break # Exit loop on success
            
        except subprocess.CalledProcessError as e:
            # Check for typical Git/SSH permission error (Exit code 128)
            is_ssh_error = (e.returncode == 128) and ("Permission denied" in e.stderr)
            
            if attempt == 0 and is_ssh_error:
                log.warning("Initial clone attempt failed due to possible missing deploy key.")
                
                # --- INTERACTIVE PROMPT TRIGGERED ONLY ON FIRST FAILURE ---
                if not exec_obj.force: # Skip if --force is used
                    ssh_dir = os.path.dirname(ssh_key_path)
                    _display_key_and_url_for_repo(
                        exec_obj, 
                        ssh_dir, 
                        repo_name, 
                        repo_url
                    )
                else:
                    log.warning("Skipping interactive deploy key prompt due to --force flag.")
                    
            elif attempt == MAX_CLONE_ATTEMPTS - 1:
                log.error("Final clone attempt failed. Abandoning repository setup.")
                raise # Re-raise the exception to stop the script
            
            else:
                # Wait before the final retry after the user has been prompted
                log.info("Waiting 5 seconds before re-trying clone after user input...")
                time.sleep(5)
                
    if not clone_succeeded:
        raise RuntimeError(f"Failed to clone repository {repo_name} after multiple attempts.")


def set_homedir_perms_recursively(exec_obj: Executor, user: str, dir_path: str) -> None:
    """Sets sane read/write permissions while preserving executable bits on files and directories."""
    log.info(f"Setting recursive permissions for {dir_path} owned by {user}")
    
    # 1. Set ownership recursively
    exec_obj.run(f"chown -R {user}:{user} {dir_path}", force_sudo=True)
    
    # 2. Set base permissions using symbolic addition/removal:
    
    # a) Set base read/write: user gets rw, group/other get r. (u+w, a+r)
    exec_obj.run(f"chmod -R a+r,u+w {dir_path}", force_sudo=True)
    
    # b) Remove write access from group and others (u+w, go-w)
    exec_obj.run(f"chmod -R go-w {dir_path}", force_sudo=True)
    
    # c) Crucial: Grant execute permission selectively (+X). 
    # '+X' only grants execute if the item is a directory OR if it already has execute permissions set for any user.
    exec_obj.run(f"chmod -R a+X {dir_path}", force_sudo=True)


def set_ssh_perms(exec_obj: Executor, user: str, ssh_dir: str) -> None:
    """Sets strict 700/.ssh and 600/keys permissions for the SSH directory."""
    log.info(f"Setting strict SSH directory permissions for {ssh_dir}")
    
    # These MUST remain strict octal/symbolic due to security requirements
    exec_obj.run(f"chmod 700 {ssh_dir}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {ssh_dir}", force_sudo=True)
    
    # Note: We rely on _create_if_needed_ssh_key to enforce 600/644 on private/public keys.
    # We still ensure all files inside have correct ownership (if the keys were newly generated by root).
    exec_obj.run(f"chown {user}:{user} {ssh_dir}/* || true", force_sudo=True)
    
    # We explicitly relax permissions on known_hosts and public keys to 644/400, just in case
    exec_obj.run(f"chmod 644 {ssh_dir}/known_hosts || true", force_sudo=True)
    exec_obj.run(f"chmod 644 {ssh_dir}/*.pub || true", force_sudo=True)