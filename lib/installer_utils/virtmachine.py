import shutil
import os
import subprocess
from ..executor import Executor
from ..logger import log
from ..constants import VM_PACKAGES, DEFAULT_VM_USER
from .apt_tools import apt_install

def setup_virtmachine(exec_obj: Executor, vm_user: str = DEFAULT_VM_USER) -> None:
    """Handles VM guest package installation and fstab setup."""
    log.info("Starting virtual machine setup...")
    
    vm_type_check = shutil.which("systemd-detect-virt")
    if not vm_type_check:
        log.warning("systemd-detect-virt not found. Cannot confirm VM status. Exiting VM setup.")
        return

    try:
        result = exec_obj.run("systemd-detect-virt", check=False, quiet=True)
        vm_type = result.stdout.strip()
    except Exception:
        vm_type = ""

    if not vm_type or vm_type == "none":
        log.warning("No VM detected. Exiting VM setup.")
        return
        
    log.success(f"Virtual machine detected: {vm_type}")

    UTM_MOUNT = "/mnt/utm"
    if not os.path.isdir(UTM_MOUNT):
        exec_obj.run(f"mkdir -p {UTM_MOUNT}", force_sudo=True)
        exec_obj.run(f"chown {vm_user}:{vm_user} {UTM_MOUNT}", force_sudo=True)
        log.success(f"Created UTM mount point: {UTM_MOUNT}")
    else:
        log.info(f"{UTM_MOUNT} already exists.")

    apt_install(exec_obj, VM_PACKAGES)

    netman_enabled = exec_obj.run("systemctl is-enabled NetworkManager-wait-online.service", check=False, quiet=True).returncode == 0
    networkd_enabled = exec_obj.run("systemctl is-enabled systemd-networkd-wait-online.service", check=False, quiet=True).returncode == 0
    
    if netman_enabled and networkd_enabled:
        log.warning("Both NetworkManager and systemd-networkd are enabled. Disabling systemd-networkd for stability.")
        exec_obj.run("systemctl disable systemd-networkd.service", force_sudo=True)

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
        return

    log.info(f"Adding fstab entry: {FSTAB_LINE}")
    exec_obj.run(f"echo \"{FSTAB_LINE}\" >> {FSTAB_FILE}", force_sudo=True)
    
    log.success("Virtual machine setup completed.")