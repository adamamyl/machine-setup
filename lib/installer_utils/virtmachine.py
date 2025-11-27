import shutil
import os
import subprocess
from typing import List, Optional
from ..executor import Executor
from ..logger import log
from ..constants import VM_PACKAGES, DEFAULT_VM_USER
from .apt_tools import apt_install

def setup_virtmachine(exec_obj: Executor, vm_user: str = DEFAULT_VM_USER) -> None:
    """Handles VM guest package installation and fstab setup."""
    log.info("Starting virtual machine setup...")
    
    vm_type_check = shutil.which("systemd-detect-virt")
    vm_type = ""
    
    # 1. Detect VM Type
    if vm_type_check:
        try:
            # Execute command, redirecting stderr to stdout (2>&1) for reliable capture
            # Note: The Executor handles exceptions internally based on returncode
            result = exec_obj.run("systemd-detect-virt 2>&1", check=False, quiet=True)
            vm_type = result.stdout.strip()
        except Exception:
            pass
            
    log.debug(f"systemd-detect-virt reported: '{vm_type}'")
            
    # 2. Check VM Status and Handle --force
    if vm_type and vm_type != "none":
        log.success(f"Virtual machine detected: {vm_type}")
    else:
        # HACKY: If detection fails, check the --force flag.
        if exec_obj.force:
            log.warning("No VM detected, but proceeding due to --force flag.")
            vm_type = "forced" # Set type for logging if needed
        else:
            log.warning("No VM detected. Exiting VM setup.")
            return # Exit only if not forced

    # --- Execution starts here (only if detected or forced) ---

    # 3. Create mount directory
    UTM_MOUNT = "/mnt/utm"
    if not os.path.isdir(UTM_MOUNT):
        exec_obj.run(f"mkdir -p {UTM_MOUNT}", force_sudo=True)
        exec_obj.run(f"chown {vm_user}:{vm_user} {UTM_MOUNT}", force_sudo=True)
        log.success(f"Created UTM mount point: {UTM_MOUNT}")
    else:
        log.info(f"{UTM_MOUNT} already exists")

    # 4. Install guest packages
    apt_install(exec_obj, VM_PACKAGES)

    # 5. Handle NetworkManager/systemd-networkd conflict
    # The Executor still logs this command, but avoids the TypeError.
    netman_enabled = exec_obj.run("systemctl is-enabled NetworkManager-wait-online.service").returncode == 0
    networkd_enabled = exec_obj.run("systemctl is-enabled systemd-networkd-wait-online.service").returncode == 0
    
    if netman_enabled and networkd_enabled:
        log.warning("Both NetworkManager and systemd-networkd are enabled. Disabling systemd-networkd for stability.")
        exec_obj.run("systemctl disable systemd-networkd.service", force_sudo=True)

    # 6. Ensure fstab entry exists (Idempotent check)
    FSTAB_LINE = "share /mnt/utm 9p trans=virtio,version=9p2000.L,rw,_netdev,nofail,auto 0 0"
    FSTAB_FILE = "/etc/fstab"
    
    entry_exists = False
    try:
        with open(FSTAB_FILE, 'r') as f:
            if any(FSTAB_LINE.strip() == line.strip() for line in f):
                entry_exists = True
    except FileNotFoundError:
        log.error(f"{FSTAB_FILE} not found. Cannot check/append fstab entry.")
        raise

    if entry_exists:
        log.success("Fstab entry already present.")
    else:
        log.info(f"Adding fstab entry: {FSTAB_LINE}")
        # Append the line using echo >>
        exec_obj.run(f"echo \"{FSTAB_LINE}\" >> {FSTAB_FILE}", force_sudo=True)
        log.success("Fstab entry added.")
    
    log.success("Virtual machine setup completed.")