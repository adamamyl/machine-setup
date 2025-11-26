import subprocess
import os
from typing import List, Optional
from ..executor import Executor
from ..logger import log

def require_user(exec_obj: Executor, user: str) -> bool:
    """Ensures a user exists, creating them with useradd -m if missing."""
    try:
        subprocess.run(['id', user], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        log.info(f"Creating user '{user}'...")
        exec_obj.run(f"useradd -m {user}", force_sudo=True)
        log.success(f"Created user '{user}'")
        return True

def add_user_to_group(exec_obj: Executor, user: str, group: str) -> None:
    """Ensures a group exists, then adds a user to it."""
    
    if not require_user(exec_obj, user):
        log.warning(f"User '{user}' does not exist, cannot add to group '{group}'")
        return

    try:
        subprocess.run(['getent', 'group', group], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        log.info(f"Creating group '{group}'...")
        exec_obj.run(f"groupadd -f {group}", force_sudo=True)
    
    try:
        result = subprocess.run(['id', '-nG', user], capture_output=True, text=True, check=True)
        if group in result.stdout.split():
            log.info(f"User '{user}' already in group '{group}'")
            return
    except subprocess.CalledProcessError:
        log.warning(f"Failed to check groups for user {user}. Attempting to add anyway.")

    exec_obj.run(f"usermod -aG {group} {user}", force_sudo=True)
    log.success(f"Added user '{user}' to group '{group}'")

def users_to_groups_if_needed(exec_obj: Executor, user: str, groups: List[str]) -> None:
    """Ensures a user exists and is a member of all specified groups."""
    require_user(exec_obj, user)
    for group in groups:
        add_user_to_group(exec_obj, user, group)

def create_if_needed_ssh_dir(exec_obj: Executor, user: str) -> str:
    """Creates the user's .ssh directory with correct permissions and ownership."""
    
    try:
        homedir_result = subprocess.run(['getent', 'passwd', user], capture_output=True, text=True, check=True)
        homedir = homedir_result.stdout.strip().split(':')[5]
    except Exception as e:
        log.error(f"Failed to get homedir for {user}: {e}")
        raise
        
    ssh_dir = os.path.join(homedir, ".ssh")
    
    exec_obj.run(f"mkdir -p -m 700 {ssh_dir}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {ssh_dir}", force_sudo=True)
    
    return ssh_dir

def install_ssh_keys(exec_obj: Executor, user: str, url: str) -> None:
    """Downloads authorized_keys from a URL and installs it for the user."""
    
    ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
    auth_keys = os.path.join(ssh_dir, "authorized_keys")

    log.info(f"Downloading SSH keys for {user} from {url}...")
    
    download_cmd = f"curl -fsSL \"{url}\" | tee \"{auth_keys}\""
    
    try:
        exec_obj.run(download_cmd, force_sudo=True)
    except Exception:
        log.error(f"Failed to download SSH keys from {url}")
        return

    exec_obj.run(f"chmod 600 {auth_keys}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {auth_keys}", force_sudo=True)
    log.success(f"Installed SSH keys for {user} from {url}")

def install_root_ssh_keys(exec_obj: Executor) -> None:
    """Installs keys for the root user from the specified GitHub account."""
    install_ssh_keys(exec_obj, "root", "https://github.com/adamamyl.keys")

def setup_sudoers_staff(exec_obj: Executor, file: str = "/etc/sudoers.d/staff") -> None:
    """Installs the NOPASSWD sudoers file for the 'staff' group."""
    content = "%staff ALL=(ALL:ALL) NOPASSWD: ALL"
    
    log.info(f"Installing sudoers file: {file}")
    
    cmd_write = f"echo \"{content}\" | tee {file} > /dev/null"
    exec_obj.run(cmd_write, force_sudo=True)
    
    exec_obj.run(f"chmod 440 {file}", force_sudo=True)
    log.success(f"Sudoers file {file} installed and permissions set to 440")