import shutil
from ..executor import Executor
from ..logger import log

def install_tailscale(exec_obj: Executor) -> None:
    """Installs Tailscale using their official curl | sh script."""
    if shutil.which("tailscale"):
        log.success("Tailscale already installed.")
        return

    log.info("Installing Tailscale...")
    exec_obj.run("curl -fsSL https://tailscale.com/install.sh | sh", force_sudo=True)
    log.success("Tailscale installation finished.")

def ensure_tailscale_strict(exec_obj: Executor) -> None:
    """Enables Tailscale SSH."""
    if not shutil.which("tailscale"):
        log.warning("Tailscale not installed, skipping strict setup.")
        return
        
    log.info("Enabling Tailscale SSH (Linux only).")
    try:
        exec_obj.run(["tailscale", "set", "--ssh"])
        log.success("Tailscale SSH enabled.")
    except Exception:
        log.warning("Failed to enable Tailscale SSH.")