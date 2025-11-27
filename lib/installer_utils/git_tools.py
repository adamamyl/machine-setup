import os
import subprocess
from typing import Optional, List
from ..executor import Executor
from ..logger import log
from ..constants import GIT_BIN_PATH # Import the dynamically resolved path

def clone_or_update_repo(exec_obj: Executor, 
                         repo_url: str, 
                         dest_dir: str, 
                         ssh_key_path: Optional[str] = None, 
                         extra_git_flags: Optional[str] = "",
                         user: Optional[str] = None) -> None:
    """
    Clones or updates a Git repository, handling SSH deploy keys if specified.
    
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
        # Define the SSH command using the deploy key
        ssh_command = f"ssh -i '{ssh_key_path}' -o IdentitiesOnly=yes"
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

# --- FIX: Preserve Executable Bits using Symbolic Mode ---
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
    log.info(f"Setting strict SSH permissions for {ssh_dir}")
    
    # These MUST remain strict octal/symbolic due to security requirements
    exec_obj.run(f"chmod 700 {ssh_dir}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {ssh_dir}", force_sudo=True)
    exec_obj.run(f"find {ssh_dir} -type f -exec chmod 600 {{}} \;", force_sudo=True)