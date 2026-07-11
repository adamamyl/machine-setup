import os
import subprocess
import tempfile
from typing import List, Optional, Set
from ..executor import Executor
from ..logger import log
from ..constants import USER_GITHUB_KEY_MAP # Required for key mapping

# --- User and Group Management ---

def _uid_gid_available(uid: int) -> bool:
    """Checks whether a uid/gid number is not already claimed by another user/group."""
    uid_taken = subprocess.run(
        ['getent', 'passwd', str(uid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0
    gid_taken = subprocess.run(
        ['getent', 'group', str(uid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0
    return not uid_taken and not gid_taken

def require_user(
    exec_obj: Executor,
    user: str,
    uid: Optional[int] = None,
    prompt_before_create: bool = False,
) -> bool:
    """
    Ensures a user exists, creating them with useradd -m if missing.

    If uid is given, tries to create the user with that uid/gid. If it's
    already claimed (e.g. by docker), falls back to the next available
    uid/gid rather than renumbering anything already on the box.

    If prompt_before_create is True and we're not running with --force,
    asks for interactive confirmation before creating the account.
    """
    try:
        # id check is idempotent
        subprocess.run(
            ['id', user], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        if prompt_before_create and not exec_obj.force and not exec_obj.dry_run:
            confirm = input(f"User '{user}' does not exist. Create it now? (y/N): ").lower()
            if confirm != 'y':
                log.warning(f"Skipping creation of user '{user}' at user's request.")
                return False

        useradd_cmd = ['useradd', '-m']
        if uid is not None:
            if _uid_gid_available(uid):
                useradd_cmd += ['-u', str(uid), '-U']
            else:
                log.warning(
                    f"uid/gid {uid} already in use (e.g. by another service); "
                    f"creating '{user}' with the next available uid/gid instead. "
                    "Not renumbering existing accounts."
                )
        useradd_cmd.append(user)

        log.info(f"Creating user '{user}'...")
        exec_obj.run(" ".join(useradd_cmd), force_sudo=True)
        log.success(f"Created user '{user}'")
        return True

ADAM_UID: int = 1000

def ensure_adam_user(exec_obj: Executor, user: str = "adam") -> bool:
    """
    Ensures the 'adam' user exists (uid/gid 1000 if available), prompting to
    create it if missing. Used by modules (root-ssh-keys, pseudohome) that
    otherwise fail hard when the account isn't there yet.
    """
    return require_user(exec_obj, user, uid=ADAM_UID, prompt_before_create=True)

def add_user_to_group(exec_obj: Executor, user: str, group: str) -> None:
    """Ensures a group exists, then adds a user to it."""
    
    if not require_user(exec_obj, user):
        log.warning(f"User '{user}' does not exist, cannot add to group '{group}'")
        return

    # Check/create group (getent is idempotent check)
    try:
        subprocess.run(
            ['getent', 'group', group],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        log.info(f"Creating group '{group}'...")
        exec_obj.run(f"groupadd -f {group}", force_sudo=True)
    
    # Check if user is already in the group (id -nG is idempotent check)
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
    """Creates the user's .ssh directory with correct permissions and ownership (Idempotent)."""
    
    try:
        homedir_result = subprocess.run(
            ['getent', 'passwd', user], capture_output=True, text=True, check=True
        )
        homedir = homedir_result.stdout.strip().split(':')[5]
    except Exception as e:
        log.error(f"Failed to get homedir for {user}: {e}")
        raise
        
    ssh_dir = os.path.join(homedir, ".ssh")
    
    exec_obj.run(f"mkdir -p -m 700 {ssh_dir}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {ssh_dir}", force_sudo=True)
    
    return ssh_dir

# --- Idempotent SSH Key Management (Deduplication) ---

def _merge_and_deduplicate_keys(existing_keys_path: str, new_keys_content: str) -> str:
    """
    Parses authorized_keys and new key content, merging and deduplicating them.
    Returns the final, cleaned content ready to be written.
    """
    
    # 1. Read existing keys (if file exists)
    existing_keys: Set[str] = set()
    if os.path.exists(existing_keys_path):
        with open(existing_keys_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                # Store non-comment keys in the set
                if stripped and not stripped.startswith('#'):
                    existing_keys.add(stripped)
    
    # 2. Read new keys content
    new_keys_list: List[str] = []
    for line in new_keys_content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            new_keys_list.append(stripped)
            
    # 3. Merge and deduplicate
    final_keys: List[str] = list(existing_keys)
    all_unique_keys: Set[str] = existing_keys.copy()
    
    # Add new keys only if they are not already present
    for key in new_keys_list:
        if key not in all_unique_keys:
            final_keys.append(key)
            all_unique_keys.add(key)
            
    return "\n".join(final_keys) + "\n"

def install_mapped_ssh_keys(exec_obj: Executor, user: str) -> None:
    """
    Installs SSH keys for a specified local user by fetching authorized_keys 
    from all mapped GitHub accounts defined in USER_GITHUB_KEY_MAP (Idempotent).
    """
    github_accounts_str = USER_GITHUB_KEY_MAP.get(user)
    
    if not github_accounts_str:
        log.warning(f"No GitHub accounts mapped for user '{user}'. Skipping key installation.")
        return

    accounts = github_accounts_str.split()
    
    log.info(f"Installing keys for user '{user}' from GitHub accounts: {', '.join(accounts)}")

    all_downloaded_keys = ""
    
    # Download keys from all mapped GitHub accounts
    for account in accounts:
        url = f"https://github.com/{account}.keys"
        log.info(f"Downloading keys from {url}...")
        
        # Use curl to download content to memory
        try:
            # We use check=False to continue fetching even if one account URL fails (e.g., 404)
            # We are relying on -f (fail silently) and -s (silent) from curl
            result = exec_obj.run(f"curl -fsSL \"{url}\"", check=False, run_quiet=True)
            if result.returncode == 0 and result.stdout.strip():
                all_downloaded_keys += result.stdout.strip() + "\n"
            else:
                log.warning(
                    f"Failed to fetch keys from {url} "
                    f"(Exit code {result.returncode} or no keys found)."
                )
        except Exception as e:
            log.error(f"Critical error during curl for {url}. Skipping this account.")
            log.debug(f"Curl error: {e}")

    if not all_downloaded_keys.strip():
        log.warning(f"No keys were successfully downloaded for user '{user}'.")
        return

    ssh_dir = create_if_needed_ssh_dir(exec_obj, user)
    auth_keys = os.path.join(ssh_dir, "authorized_keys")
    
    # Merge, deduplicate, and get final content
    final_content = _merge_and_deduplicate_keys(auth_keys, all_downloaded_keys)

    # --- Idempotency Check: Write only if content has changed ---
    current_content = ""
    if os.path.exists(auth_keys):
        # Read current content for comparison
        with open(auth_keys, 'r') as f:
            current_content = f.read()
            
    # Check if content has changed (ignoring surrounding whitespace/trailing newlines)
    if current_content.strip() == final_content.strip() and not exec_obj.force:
        log.success(f"SSH keys for {user} are up-to-date and deduplicated.")
        return
        
    log.info(f"Writing updated and deduplicated authorized_keys for {user}...")
    
    with tempfile.NamedTemporaryFile(mode='w', prefix='authorized_keys_', delete=False) as tmp:
        tmp.write(final_content)
        temp_final_file = tmp.name

    exec_obj.run(f"mv \"{temp_final_file}\" \"{auth_keys}\"", force_sudo=True)
    
    # Fix permissions/ownership (Idempotent fix)
    exec_obj.run(f"chmod 600 {auth_keys}", force_sudo=True)
    exec_obj.run(f"chown {user}:{user} {auth_keys}", force_sudo=True)
    log.success(f"Installed/Updated SSH keys for {user}, duplicates removed.")


def install_root_ssh_keys(exec_obj: Executor) -> None:
    """Installs keys for the root user using the centralized map."""
    install_mapped_ssh_keys(exec_obj, "root")

# --- Sudoers ---

def setup_sudoers_staff(exec_obj: Executor, file: str = "/etc/sudoers.d/staff") -> None:
    """Installs the NOPASSWD sudoers file for the 'staff' group (Idempotent)."""
    content = "%staff ALL=(ALL:ALL) NOPASSWD: ALL"
    
    # Check if the file exists and contains the exact content
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                if content.strip() in f.read().strip():
                    log.success(f"Sudoers file {file} already contains the correct content.")
                else:
                    log.info(f"Sudoers file {file} exists but content differs. Overwriting.")
                    # Fall through to write logic
        except Exception:
             log.warning(f"Could not read {file}. Overwriting to ensure correctness.")
             # Fall through to write logic
    
    log.info(f"Installing sudoers file: {file}")
    
    # Write the content using tee (handles privilege)
    cmd_write = f"echo \"{content}\" | tee {file} > /dev/null"
    exec_obj.run(cmd_write, force_sudo=True)
    
    # Fix permissions
    exec_obj.run(f"chmod 440 {file}", force_sudo=True)
    log.success(f"Sudoers file {file} installed and permissions set to 440")