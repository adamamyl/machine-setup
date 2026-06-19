import os
from ..executor import Executor
from ..logger import log
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import (
    clone_or_update_private_repo_with_key_check,
    set_homedir_perms_recursively,
    set_ssh_perms,
)
from .repo_utils import _create_if_needed_ssh_key
from .ssh_utils import probe_and_fix_ssh
from .tailscale import ensure_tailscale_connected

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
    _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)

    # Ensure the .ssh directory itself has strict permissions before use
    set_ssh_perms(exec_obj, user, ssh_dir)

    # 3. Tailscale Connection Check (Prerequisite for git.amyl.org.uk)
    log.info("Checking Tailscale connection for git.amyl.org.uk access...")
    if not ensure_tailscale_connected(exec_obj):
        raise RuntimeError(
            "Tailscale not connected — cannot reach git.amyl.org.uk. Aborting pseudohome setup."
        )

    # 4. SSH connectivity probe — remediates known_hosts / key perms, prompts if key missing
    ssh_key_path = os.path.join(ssh_dir, repo_name)
    log.info("Probing SSH connectivity to git.amyl.org.uk...")
    probe_and_fix_ssh(
        exec_obj,
        host="git.amyl.org.uk",
        ssh_user=user,
        key_path=ssh_key_path,
    )

    # 5. Clone/Update Repo (Handles interactive key prompt and retry on failure)

    clone_or_update_private_repo_with_key_check(
        exec_obj,
        PSEUDOHOME_REPO_URL,
        dest_dir,
        ssh_key_path=ssh_key_path,
        repo_name=repo_name,
        extra_git_flags="--recursive",
        user=user,  # Execute as 'adam'
    )

    # 6. Fix permissions: home dir ownership (non-recursive — must not clobber .ssh),
    # then repo contents, then re-enforce .ssh in case anything above touched it.
    exec_obj.run(f"chown {user}:{user} {os.path.dirname(dest_dir)}", force_sudo=True)
    set_homedir_perms_recursively(exec_obj, user, dest_dir)
    set_ssh_perms(exec_obj, user, ssh_dir)

    # 7. Run installer script (as the user)
    installer_path = os.path.join(dest_dir, PSEUDOHOME_INSTALLER)
    if os.path.exists(installer_path) and os.access(installer_path, os.X_OK):
        log.info("Running pseudohome installer script...")
        exec_obj.run([installer_path], user=user)
    else:
        log.warning(f"Installer {PSEUDOHOME_INSTALLER} not executable, skipping.")

    log.success(f"Pseudohome setup complete for {user}.")
