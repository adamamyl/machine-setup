import os
import sys
import platform
import re
from typing import Optional
from ..executor import Executor
from ..logger import log
from ..constants import HWGA_REPOS


def _convert_ssh_to_deploy_url(ssh_url: str) -> str:
    # ... (function body remains the same) ...
    
    if ssh_url.startswith("git@github.com:"):
        path = ssh_url.replace("git@github.com:", "https://github.com/")
    elif ssh_url.startswith("git@gitlab.com:"):
        path = ssh_url.replace("git@gitlab.com:", "https://gitlab.com/")
    elif ssh_url.startswith("adam@git.amyl.org.uk:"):
        return ssh_url
    else:
        return ssh_url
    
    path = re.sub(r'\.git$', '', path)
    return path + '/settings/keys'


def _create_if_needed_ssh_key(exec_obj: Executor, user: str, ssh_dir: str, key_name: str) -> bool: # <-- MODIFIED RETURN TYPE
    """
    Generates an ED25519 SSH key if it doesn't exist.
    Returns True if a new key was generated, False if skipped.
    """
    key_file = os.path.join(ssh_dir, key_name)
    
    # 1. IDEMPOTENCY CHECK: Skip if the private key file already exists.
    if os.path.isfile(key_file):
        log.success(f"SSH key for {key_name} already exists. Skipping generation.")
        return False # <-- RETURN FALSE

    # 2. CONSTRUCT COMMENT (Remains the same)
    host_name = platform.node()
    comment = f"'{user}@{host_name}/{key_name}'"
    
    repo_url = None
    config = HWGA_REPOS.get(key_name)
    
    if config:
        repo_url = config.get('url')

    if repo_url and ('@github.com' in repo_url or '@gitlab.com' in repo_url):
        parts = repo_url.split(':')[-1].replace('.git', '')
        comment = f"'{user}@{host_name}/{parts}'"
        
    log.info(f"Generating SSH key for {key_name} for user {user} (Comment: {comment})...")
    
    # 3. RUN SSH-KEYGEN
    cmd = [
        'ssh-keygen', '-t', 'ed25519', '-f', key_file, 
        '-N', '', '-C', comment 
    ]
    exec_obj.run(cmd, user=user) 
    
    # 4. FIX PERMISSIONS/OWNERSHIP
    exec_obj.run(f"chmod 600 {key_file}", force_sudo=True) 
    exec_obj.run(f"chown {user}:{user} {key_file}*", force_sudo=True)
    log.success(f"Generated SSH key pair: {key_name}")
    
    return True # <-- RETURN TRUE IF GENERATED


def _display_key_and_url_for_repo(exec_obj: Executor, ssh_dir: str, repo_name: str, repo_url: str) -> None:
    # ... (function body remains the same) ...
    
    # (The function body which displays the key and waits for input remains the same)
    # (It relies on the caller to decide if it should be called at all)
    
    deploy_url = _convert_ssh_to_deploy_url(repo_url)
    
    # --- OUTPUT FIXES ---
    print("\n" + "="*70)
    log.warning(f"🔗 DEPLOYMENT LINK: Add public key to: {deploy_url}")
    log.info(f"The public key for **{repo_name}** is:")
    print("="*70 + "\n", flush=True)
    
    try:
        with open(key_file_pub, 'r') as f:
            pub_key = f.read().strip()
            print("\n" + "="*50, flush=True)
            print(pub_key, flush=True)
            print("="*50 + "\n", flush=True)
            
    except FileNotFoundError:
        log.error(f"Public key file not found at {key_file_pub}")
        raise
        
    input("Press Enter once the deploy key has been successfully added to the Git host...")