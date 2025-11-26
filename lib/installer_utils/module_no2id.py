import os
import sys
from typing import List, Dict
import platform
from ..executor import Executor
from ..logger import log
from ..constants import HWGA_REPOS, ROOT_SRC_CHECKOUT, SYSTEM_REPOS
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import clone_or_update_repo, set_homedir_perms_recursively, set_ssh_perms

def _display_key_and_url_for_repo(ssh_dir: str, repo_name: str, repo_url: str) -> None:
    """Displays public key, URL, and prompts for confirmation."""
    key_file_pub = os.path.join(ssh_dir, f"{repo_name}.pub")

    log.info(f"Add the following public key as a deploy key to **{repo_url}** for **{repo_name}**:")
    
    try:
        with open(key_file_pub, 'r') as f:
            pub_key = f.read().strip()
            print("\n" + "="*50)
            print(pub_key)
            print("="*50 + "\n")
    except FileNotFoundError:
        log.error(f"Public key file not found at {key_file_pub}")
        raise
        
    log.info(f"Deploy key URL: {repo_url}")
    input("Press Enter once the deploy key has been successfully added to the Git host...")

def _create_if_needed_ssh_key(exec_obj: Executor, user: str, ssh_dir: str, key_name: str) -> None:
    """Generates an ED25519 SSH key if it doesn't exist."""
    key_file = os.path.join(ssh_dir, key_name)
    
    if not os.path.isfile(key_file):
        log.info(f"Generating SSH key for {key_name} for user {user}...")
        
        cmd = [
            'ssh-keygen', '-t', 'ed25519', '-f', key_file, 
            '-N', '', '-C', f"'{user}@{platform.node()}'"
        ]
        
        exec_obj.run(cmd, user=user) 
        
        exec_obj.run(f"chmod 600 {key_file}", force_sudo=True)
        exec_obj.run(f"chown {user}:{user} {key_file}*", force_sudo=True)
        log.success(f"Generated SSH key pair: {key_name}")


def install_system_repos(exec_obj: Executor) -> None:
    """Installs and runs installers for system-level GitHub repos."""
    log.info("Starting installation of system-level repositories...")

    base_dir = ROOT_SRC_CHECKOUT
    exec_obj.run(f"mkdir -p {base_dir}", force_sudo=True)
    exec_obj.run(f"chgrp docker {base_dir} || true", force_sudo=True)
    exec_obj.run(f"chmod g+w {base_dir}", force_sudo=True)
    exec_obj.run(f"chmod -s {base_dir}", force_sudo=True)

    for repo_name, config in SYSTEM_REPOS.items():
        installer = config['installer']
        repo_url = config['url']
        dest_dir = os.path.join(base_dir, repo_name)

        clone_or_update_repo(exec_obj, repo_url, dest_dir)

        exec_obj.run(f"chown -R root:root {dest_dir}", force_sudo=True)
        exec_obj.run(f"chmod -R g+w {dest_dir}", force_sudo=True)
        exec_obj.run(f"chmod -s {dest_dir}", force_sudo=True)

        install_path = os.path.join(dest_dir, installer)
        if os.path.exists(install_path) and os.access(install_path, os.X_OK):
            log.info(f"Running {installer} for {repo_name}...")
            exec_obj.run(f"pushd '{dest_dir}' >/dev/null && './{installer}' && popd >/dev/null", force_sudo=True)
            log.success(f"Installer completed for {repo_name}.")
        else:
            log.warning(f"Installer {install_path} missing or not executable, skipping.")
    log.success("System repository installation finished.")


def setup_no2id(exec_obj: Executor, venv_dir: str) -> None:
    """Setup no2id-docker user, groups, SSH keys, and clone/update the NO2ID repos."""
    log.info("Starting **NO2ID** setup...")
    
    exec_obj.run(f"mkdir -p {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chgrp docker {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chmod g+w {ROOT_SRC_CHECKOUT}", force_sudo=True)
    exec_obj.run(f"chmod -s {ROOT_SRC_CHECKOUT}", force_sudo=True)

    for repo_name, config in HWGA_REPOS.items():
        user = config['user']
        dest_dir = config['dest']
        repo_url = config['url']
        installer = config['installer']
        extra_flags = config['extra_flags']
        
        log.info(f"Processing repository: {repo_name} for user: {user}")

        groups = ["docker"]
        if user == "adam":
            groups.append("staff")
        users_to_groups_if_needed(exec_obj, user, groups)

        ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
        _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)
        
        _display_key_and_url_for_repo(ssh_dir, repo_name, repo_url)
        
        ssh_key_path = os.path.join(ssh_dir, repo_name)
        clone_or_update_repo(exec_obj, repo_url, dest_dir, ssh_key_path, extra_flags)
        
        set_homedir_perms_recursively(exec_obj, user, dest_dir)
        set_ssh_perms(exec_obj, user, ssh_dir)

        install_path = os.path.join(dest_dir, installer)
        if os.path.exists(install_path) and os.access(install_path, os.X_OK):
            log.info(f"Running installer {installer} for {repo_name} as user {user}...")
            
            env_vars = {
                "VENVDIR": venv_dir,
                "PATH": f"{venv_dir}/bin:{os.environ.get('PATH', '')}"
            }
            exec_obj.run(f"'{install_path}'", user=user, env=env_vars)
        else:
            log.warning(f"Installer {installer} for {repo_name} not executable, skipping.")

    log.success("NO2ID setup complete.")