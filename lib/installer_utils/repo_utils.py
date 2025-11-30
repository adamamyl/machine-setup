import os
import sys
import platform
import re
from typing import Optional, List
from ..executor import Executor
from ..logger import log
from ..constants import HWGA_REPOS, TOOLS_DIR


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


def _create_if_needed_ssh_key(exec_obj: Executor, user: str, ssh_dir: str, key_name: str) -> bool:
    """
    Generates an ED25519 SSH key if it doesn't exist.
    ENSURES strict permissions are set on the private key regardless of creation status.
    Returns True if a new key was generated, False if skipped.
    """
    key_file = os.path.join(ssh_dir, key_name)
    key_file_pub = f"{key_file}.pub"
    key_exists = os.path.isfile(key_file)
    key_is_new = False

    # 1. GENERATION: Skip if the private key file already exists.
    if key_exists:
        log.success(f"SSH key for {key_name} already exists. Skipping generation.")
        key_is_new = False
    else:
        # 2. CONSTRUCT COMMENT and RUN SSH-KEYGEN
        host_name = platform.node()
        
        # Determine comment based on repo URL (use default if not found)
        comment_suffix = f"'{user}@{host_name}/{key_name}'"
        repo_url = HWGA_REPOS.get(key_name, {}).get('url')
        
        if repo_url and ('@github.com' in repo_url or '@gitlab.com' in repo_url):
            parts = repo_url.split(':')[-1].replace('.git', '')
            comment_suffix = f"'{user}@{host_name}/{parts}'"
            
        log.info(f"Generating SSH key for {key_name} for user {user} (Comment: {comment_suffix})...")
        
        cmd = [
            'ssh-keygen', '-t', 'ed25519', '-f', key_file, 
            '-N', '', '-C', comment_suffix # -N '' ensures no passphrase
        ]
        exec_obj.run(cmd, user=user) 
        log.success(f"Generated SSH key pair: {key_name}")
        key_is_new = True

    # --- 3. PERMISSION ENFORCEMENT (ALWAYS RUNS IF KEY FILE EXISTS) ---
    if os.path.isfile(key_file):
        log.info(f"Enforcing strict permissions and ownership on {key_name} keys...")

        # Set ownership for both private and public keys
        exec_obj.run(f"chown {user}:{user} {key_file} {key_file_pub}", force_sudo=True)
        
        # Enforce strict 600 permissions on the PRIVATE key (crucial for SSH)
        exec_obj.run(f"chmod 600 {key_file}", force_sudo=True)
        
        # Ensure public key is readable (e.g., 644)
        exec_obj.run(f"chmod 644 {key_file_pub}", force_sudo=True)
        
        log.success(f"Permissions for {key_name} keys enforced.")
    # ------------------------------------------------------------------
    
    return key_is_new


def _display_key_and_url_for_repo(exec_obj: Executor, ssh_dir: str, repo_name: str, repo_url: str) -> None:
    # ... (function body remains the same) ...
    
    deploy_url = _convert_ssh_to_deploy_url(repo_url)
    
    # FIX: Define key_file_pub before use
    key_file_pub = os.path.join(ssh_dir, f"{repo_name}.pub")

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

# --- NEW DOTENV SYNC UTILITY ---
def _dotenv_sync_if_needed(exec_obj: Executor, repo_name: str, user: str, repo_dir: str) -> None:
    """
    Checks if a repository is configured for environment file synchronization and runs the script.
    """
    config = HWGA_REPOS.get(repo_name, {})
    
    if not config.get("dotenv_sync"): # <-- CHECKING RENAMED FLAG
        return

    script_name = "env-generator.py" 
    script_path = os.path.join(TOOLS_DIR, script_name)
    
    if not os.path.exists(script_path):
        log.critical(f"Env generator script not found at {script_path}. Cannot generate .env.")
        raise FileNotFoundError(f"Missing {script_path}")

    output_file = os.path.join(repo_dir, ".env")

    # If the .env file already exists, we skip generation unless forced.
    if os.path.exists(output_file) and not exec_obj.force:
        log.success(f".env file already exists in {repo_dir}. Skipping synchronization.")
        return

    log.info(f"Generating .env file in {repo_dir} for user {user}...")
    
    # We call the external Python script directly
    cmd_list = [
        "python3",
        script_path,
        # "--env", "prod" # Defaulting to 'prod' or a sensible default for servers
    ]
    
    # Propagate dry-run status to the external script
    if exec_obj.dry_run:
        cmd_list.append("--dry-run")
    
    # Run the script as the target user, specifying the repo dir as the current working directory.
    exec_obj.run(cmd_list, user=user, cwd=repo_dir, check=True, interactive=True)
    log.success(f"Generated and secured {repo_dir}/.env file.")