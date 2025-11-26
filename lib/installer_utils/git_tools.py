import os
import subprocess
from typing import Optional, List
from ..executor import Executor
from ..logger import log

def clone_or_update_repo(exec_obj: Executor, 
                         repo_url: str, 
                         dest_dir: str, 
                         ssh_key_path: Optional[str] = None, 
                         extra_git_flags: Optional[str] = "") -> None:
    """
    Clones or updates a Git repository, handling SSH deploy keys if specified.
    """
    
    parent_dir = os.path.dirname(dest_dir)
    
    # 1. Ensure parent dir exists and has correct group/permissions
    exec_obj.run(f"mkdir -p {parent_dir}", force_sudo=True)
    
    exec_obj.run(f"chgrp -R docker {parent_dir} || true", force_sudo=True)
    exec_obj.run(f"chmod -R g+w {parent_dir}", force_sudo=True)
    exec_obj.run(f"chmod -R -s {parent_dir} || true", force_sudo=True)

    # 2. Prepare environment for SSH key usage
    env_vars = {}
    if ssh_key_path:
        env_vars['GIT_SSH_COMMAND'] = f"ssh -i '{ssh_key_path}' -o IdentitiesOnly=yes"
        log.debug(f"Using GIT_SSH_COMMAND: {env_vars['GIT_SSH_COMMAND']}")
    
    # 3. Check if repo exists and handle update/integrity
    if os.path.isdir(os.path.join(dest_dir, ".git")):
        try:
            # Check integrity
            exec_obj.run(['git', '-C', dest_dir, 'rev-parse', '--is-inside-work-tree'], env=env_vars)
            
            # Update
            log.info(f"Updating existing repository: {dest_dir}")
            exec_obj.run(['git', '-C', dest_dir, 'fetch', '--all', '--prune'], env=env_vars)
            log.success(f"Repository updated: {dest_dir}")
            
        except Exception:
            # Integrity check or fetch failed -> Remove and re-clone
            log.warning(f"Repo integrity check or fetch failed at {dest_dir}; removing and recloning.")
            exec_obj.run(f"rm -rf {dest_dir}", force_sudo=True)
        
    # 4. Clone if missing or just removed
    if not os.path.isdir(os.path.join(dest_dir, ".git")):
        log.info(f"Cloning {repo_url} -> {dest_dir}")
        
        clone_cmd: List[str] = ['git', 'clone']
        
        if extra_git_flags:
            clone_cmd.extend(extra_git_flags.split())

        clone_cmd.extend([repo_url, dest_dir])

        exec_obj.run(clone_cmd, env=env_vars)
        log.success(f"Repository cloned: {dest_dir}")

def set_homedir_perms_recursively(exec_obj: Executor, user: str, dir_path: str) -> None:
    """Sets standard 644/755 permissions and corrects ownership for a home directory."""
    log.info(f"Setting recursive permissions for {dir_path} owned by {user}")
    exec_obj.run(f"chown -R {user}:{user} {dir_path}", force_sudo=True)
    exec_obj.run(f"find {dir_path} -type f -exec chmod 644 {{}} \\;", force_sudo=True)
    exec_obj.run(f"find {dir_path} -type d -exec chmod 755 {{}} \\;", force_sudo=True)

def set_ssh_perms(exec_obj: Executor, user: str, ssh_dir: str) -> None:
    """Sets strict 700/.ssh and 600/keys permissions for the SSH directory."""
    log.info(f"Setting strict SSH permissions for {ssh_dir}")
    exec_obj.run(f"chmod 700 {ssh_dir}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {ssh_dir}", force_sudo=True)
    exec_obj.run(f"find {ssh_dir} -type f -exec chmod 600 {{}} \\;", force_sudo=True)