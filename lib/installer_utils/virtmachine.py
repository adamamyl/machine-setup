import shutil
import os
import subprocess
from typing import List, Optional, Tuple
from ..executor import Executor
from ..logger import log
from ..constants import VM_PACKAGES, DEFAULT_VM_USER
from .apt_tools import apt_install

# --- New Helper Function for ID Detection ---

def _get_current_bindfs_ids(exec_obj: Executor, mount_point: str = "/mnt/utm") -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to read the UID and GID of the mount point to find mismatched ownership.
    Returns (uid, gid) as strings, or (None, None) if unsuccessful.
    """
    log.info(f"Checking current UID/GID ownership of {mount_point}...")
    
    # We must ensure the mount is present before checking ownership.
    if not os.path.ismount(mount_point):
        log.warning(f"Mount point {mount_point} is not yet mounted. Cannot determine UID/GID mismatch.")
        return None, None
        
    # Get ownership of the mount point itself (using ls -nd)
    # Example output: drwxr-xr-x 4 502 20 128 Feb 22 15:52 .
    # We use stat -c to get raw UID/GID: %u %g
    try:
        # Running 'stat' requires root if ownership is non-root
        result = exec_obj.run(f"stat -c '%u %g' {mount_point}", run_quiet=True)
        uid, gid = result.stdout.strip().split()
        log.info(f"Detected UID/GID mismatch: {uid}:{gid}")
        return uid, gid
    except Exception as e:
        log.warning(f"Could not reliably determine current UID/GID for bindfs mapping.")
        log.debug(f"Stat error: {e}")
        return None, None


# --- Main Function ---

def setup_virtmachine(exec_obj: Executor, vm_user: str = DEFAULT_VM_USER, force_detection: bool = False) -> None:
    """Handles VM guest package installation, fstab setup, and bindfs remapping."""
    log.info("Starting virtual machine setup...")
    
    vm_type_check = shutil.which("systemd-detect-virt")
    vm_type = ""
    
    # 1. Detect VM Type
    # ... (VM detection logic remains the same, relies on --force if needed) ...
    if vm_type_check:
        try:
            result = exec_obj.run("systemd-detect-virt 2>&1", check=False, quiet=True)
            vm_type = result.stdout.strip()
        except Exception:
            pass
            
    log.debug(f"systemd-detect-virt reported: '{vm_type}'")
            
    # 2. Check VM Status and Handle --vm-force
    if vm_type and vm_type != "none":
        log.success(f"Virtual machine detected: {vm_type}")
    else:
        # Check 2: If detection fails, check the specific force flag.
        if force_detection: # <-- Check the new flag here
            log.warning("No VM detected, but proceeding due to --vm-force flag.")
            vm_type = "forced"
        else:
            log.warning("No VM detected. Exiting VM setup.")
            return # Exit only if not forced
        
    # --- Execution starts here ---
    UTM_MOUNT = "/mnt/utm"
    USER_MOUNT = f"/home/{vm_user}/utm"
    
    # 2. Create base mount directory
    if not os.path.isdir(UTM_MOUNT):
        exec_obj.run(f"mkdir -p {UTM_MOUNT}", force_sudo=True)
        exec_obj.run(f"chown {vm_user}:{vm_user} {UTM_MOUNT}", force_sudo=True)
        log.success(f"Created UTM mount point: {UTM_MOUNT}")
    else:
        log.info(f"{UTM_MOUNT} already exists")

    # 3. Install guest packages (includes bindfs dependency)
    # apt_install handles idempotency and apt update
    VM_PACKAGES_FULL = VM_PACKAGES + ["bindfs"]
    apt_install(exec_obj, VM_PACKAGES_FULL)

    # 4. Handle NetworkManager/systemd-networkd conflict (unchanged)
    # The Executor still logs this command, but avoids the TypeError.
    netman_enabled = exec_obj.run("systemctl is-enabled NetworkManager-wait-online.service").returncode == 0
    networkd_enabled = exec_obj.run("systemctl is-enabled systemd-networkd-wait-online.service").returncode == 0
    
    if netman_enabled and networkd_enabled:
        log.warning("Both NetworkManager and systemd-networkd are enabled. Disabling systemd-networkd for stability.")
        exec_obj.run("systemctl disable systemd-networkd.service", force_sudo=True)

    # 5. Ensure fstab entry for the *initial* mount exists (unchanged)
    FSTAB_LINE_VIRTIO = "share /mnt/utm 9p trans=virtio,version=9p2000.L,rw,_netdev,nofail,auto 0 0"
    FSTAB_FILE = "/etc/fstab"
    
    entry_exists = False
    try:
        with open(FSTAB_FILE, 'r') as f:
            if any(FSTAB_LINE_VIRTIO.strip() == line.strip() for line in f):
                entry_exists = True
    except FileNotFoundError:
        log.error(f"{FSTAB_FILE} not found. Cannot check/append fstab entry.")
        raise

    if entry_exists:
        log.success("Initial fstab entry (9p) already present.")
    else:
        log.info(f"Adding initial fstab entry: {FSTAB_LINE_VIRTIO}")
        exec_obj.run(f"echo \"{FSTAB_LINE_VIRTIO}\" >> {FSTAB_FILE}", force_sudo=True)
        log.success("Initial fstab entry added.")

    # ------------------------------------------------------------------
    # 6. Bindfs Setup: Systemd Reload, Mount Check, and Remap Setup
    # ------------------------------------------------------------------

    # 6a. Force systemd to recognize new fstab entry
    log.info("Running systemctl daemon-reload and network target restart.")
    exec_obj.run("systemctl daemon-reload", force_sudo=True)

    # Determine which target to restart (network-fs.target is standard; remote-fs.target is fallback)
    target_fs = "network-fs.target"
    try:
        # Check if the primary target exists before restarting
        exec_obj.run(f"systemctl status {target_fs}", check=True)
    except Exception:
        log.warning(f"Target {target_fs} not found. Falling back to remote-fs.target.")
        target_fs = "remote-fs.target"
        
    exec_obj.run(f"systemctl restart {target_fs}", force_sudo=True)
    
    # 6b. Check for successful initial mount and get IDs
    log.info("Verifying initial 9p mount and determining mismatched UIDs.")
    mismatched_uid, mismatched_gid = _get_current_bindfs_ids(exec_obj, UTM_MOUNT)

    # Get the target user's local UID/GID (adam:adam is typically 1000:1000)
    target_uid = subprocess.run(['id', '-u', vm_user], capture_output=True, text=True, check=True).stdout.strip()
    target_gid = subprocess.run(['id', '-g', vm_user], capture_output=True, text=True, check=True).stdout.strip()

    # 6c. Create user mount point
    exec_obj.run(f"mkdir -p {USER_MOUNT}", force_sudo=True)
    exec_obj.run(f"chown {vm_user}:{vm_user} {USER_MOUNT}", force_sudo=True)
    log.success(f"Created user mount point: {USER_MOUNT}")

    # 6d. Build and ensure bindfs fstab entry
    if mismatched_uid and mismatched_gid:
        # map=502/1000:@20/@1000
        map_string = f"map={mismatched_uid}/{target_uid}:@{mismatched_gid}/@{target_gid}"
    else:
        # Fallback to common defaults if detection failed (still more informative than nothing)
        log.warning("Using fallback bindfs map to 1000:1000 as IDs could not be confirmed.")
        map_string = f"map=1000/{target_uid}:@1000/@{target_gid}"

    FSTAB_LINE_BINDFS = f"{UTM_MOUNT} {USER_MOUNT} fuse.bindfs {map_string},x-systemd.requires={UTM_MOUNT},_netdev,nofail,auto 0 0"

    # Check/add bindfs fstab entry (similar idempotency logic)
    bindfs_entry_exists = False
    try:
        with open(FSTAB_FILE, 'r') as f:
            if any(FSTAB_LINE_BINDFS.strip() == line.strip() for line in f):
                bindfs_entry_exists = True
    except Exception:
        pass # Ignore

    if bindfs_entry_exists:
        log.success("Bindfs fstab entry already present.")
    else:
        log.info(f"Adding bindfs fstab entry: {FSTAB_LINE_BINDFS}")
        exec_obj.run(f"echo \"{FSTAB_LINE_BINDFS}\" >> {FSTAB_FILE}", force_sudo=True)
        log.success("Bindfs fstab entry added.")
        
    log.success("Virtual machine setup completed.")