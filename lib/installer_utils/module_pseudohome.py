import os
import platform
import time
from ..executor import Executor
from ..logger import log
from .user_mgmt import users_to_groups_if_needed, create_if_needed_ssh_dir
from .git_tools import (
    clone_or_update_private_repo_with_key_check,
    set_homedir_perms_recursively,
    set_ssh_perms,
)
from .repo_utils import _create_if_needed_ssh_key, _display_key_and_url_for_repo
from .ssh_utils import probe_and_fix_ssh
from .tailscale import ensure_tailscale_connected

# Constants
PSEUDOHOME_USER: str = "adam"
PSEUDOHOME_REPO_NAME: str = "pseudohome"
PSEUDOHOME_REPO_URL: str = "adam@git.amyl.org.uk:/data/git/pseudoadam"
PSEUDOHOME_DEST_DIR: str = os.path.join(f"/home/{PSEUDOHOME_USER}", PSEUDOHOME_REPO_NAME)
PSEUDOHOME_INSTALLER: str = "pseudohome-symlinks"


def _show_wolfcraig_copy_hint(exec_obj: Executor, user: str, ssh_dir: str, repo_name: str) -> None:
    # Prefer the Tailscale IP: it's reachable regardless of LAN/mDNS, unlike a
    # bare hostname (which needs .local mDNS on the same network to resolve,
    # and this box may not be on one — e.g. a cloud VM).
    hostname = platform.node()
    address = hostname
    try:
        result = exec_obj.run("tailscale ip -4", check=True, run_quiet=True, force_sudo=True)
        ts_ip = result.stdout.strip()
        if ts_ip:
            address = ts_ip
    except Exception as e:
        log.debug(f"Could not determine Tailscale IP for copy hint: {e}")

    pub_key_path = os.path.join(ssh_dir, f"{repo_name}.pub")
    cmd = (
        f"ssh {user}@{address} 'cat {pub_key_path}' "
        f"| ssh {user}@wolfcraig 'cat >> ~/.ssh/authorized_keys'"
    )
    print("\n" + "=" * 70, flush=True)
    log.warning(
        "ACTION REQUIRED: run this on your LOCAL machine to authorise the deploy key on wolfcraig:"
    )
    print("=" * 70, flush=True)
    if address == hostname:
        log.warning(
            f"Could not determine a Tailscale IP; using bare hostname '{address}', "
            "which only resolves on the same LAN (no .local mDNS assumed). Swap it "
            "for a reachable hostname/IP if the command below doesn't connect:"
        )
    print(f"\n  {cmd}\n", flush=True)
    print("=" * 70 + "\n", flush=True)
    for i in range(10, 0, -1):
        print(f"  Continuing in {i}s...  ", end="\r", flush=True)
        time.sleep(1)
    print(flush=True)


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
    key_is_new = _create_if_needed_ssh_key(exec_obj, user, ssh_dir, repo_name)

    if key_is_new:
        _show_wolfcraig_copy_hint(exec_obj, user, ssh_dir, repo_name)

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
    ssh_ok = probe_and_fix_ssh(
        exec_obj,
        host="git.amyl.org.uk",
        ssh_user=user,
        key_path=ssh_key_path,
    )
    if not ssh_ok and not exec_obj.force:
        log.warning(
            "Cannot reach git.amyl.org.uk — the pseudohome deploy key may not be authorised yet."
        )
        _display_key_and_url_for_repo(exec_obj, ssh_dir, repo_name, PSEUDOHOME_REPO_URL)

    # 5. Clone/Update Repo — always re-enforce .ssh perms even if clone fails.
    try:
        clone_or_update_private_repo_with_key_check(
            exec_obj,
            PSEUDOHOME_REPO_URL,
            dest_dir,
            ssh_key_path=ssh_key_path,
            repo_name=repo_name,
            extra_git_flags="--recursive",
            user=user,
        )

        # 6. Fix permissions on repo dir; home dir chown is non-recursive.
        exec_obj.run(f"chown {user}:{user} {os.path.dirname(dest_dir)}", force_sudo=True)
        set_homedir_perms_recursively(exec_obj, user, dest_dir)
    finally:
        # Always re-enforce .ssh and home dir ownership — guard against any upstream group leak.
        # /home/adam must never carry the docker group; adam:adam only.
        exec_obj.run(f"chown {user}:{user} /home/{user}", force_sudo=True)
        set_ssh_perms(exec_obj, user, ssh_dir)

    # 7. Run installer script (as the user)
    installer_path = os.path.join(dest_dir, PSEUDOHOME_INSTALLER)
    if os.path.exists(installer_path) and os.access(installer_path, os.X_OK):
        log.info("Running pseudohome installer script...")
        exec_obj.run([installer_path], user=user)
    else:
        log.warning(f"Installer {PSEUDOHOME_INSTALLER} not executable, skipping.")

    log.success(f"Pseudohome setup complete for {user}.")
