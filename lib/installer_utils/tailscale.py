import shutil
from ..executor import Executor
from ..logger import log
import subprocess # Added for specific error handling
import time # Added for sleep in retry logic

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
        # Note: tailscale commands typically need sudo/root privilege to interact with the service
        exec_obj.run(["tailscale", "set", "--ssh"], force_sudo=True)
        log.success("Tailscale SSH enabled.")
    except Exception:
        log.warning("Failed to enable Tailscale SSH.")

def ensure_tailscale_connected(exec_obj: Executor) -> bool:
    """
    Checks if tailscale is connected, and if not, prompts to log in (with retry).
    Uses 'tailscale ip -4' as a robust status check.
    Returns True if connected or successfully connected, False otherwise.
    """
    if not shutil.which("tailscale"):
        log.warning("Tailscale not installed. Cannot ensure tailnet connection.")
        return False

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        
        # 1. Check connection status using a robust command (tailscale ip -4)
        try:
            # Running as root (force_sudo=True) to ensure interaction with the system service.
            # check=True will raise CalledProcessError if not logged in/service is down.
            result = exec_obj.run("tailscale ip -4", check=True, run_quiet=True, force_sudo=True)
            
            # Check if the output is a valid IPv4 address (a sign of a successful connection)
            if result.stdout.strip() and "." in result.stdout.strip():
                log.success(f"Tailscale already connected (IP: {result.stdout.strip()}).")
                return True
            else:
                # Should not happen if check=True succeeded, but acts as a safeguard
                log.info(f"Tailscale IP found but seems invalid. Proceeding to 'up'.")

        except subprocess.CalledProcessError: 
            # This is the expected failure if the service is up but not logged in, or the daemon is starting.
            log.info(f"Tailscale IP check failed (service/login issue, Attempt {attempt + 1}/{MAX_RETRIES}). Proceeding to 'up'.")
            if attempt == MAX_RETRIES - 1:
                break
            
        except Exception as e:
            # Catch unexpected execution issues like OSError (was likely the original problem)
            log.warning(f"Tailscale status check caused internal error: {e}. Proceeding to 'up'.")
            if attempt == MAX_RETRIES - 1:
                break


        # 2. Attempt Interactive Login
        log.info("Initiating interactive 'tailscale up' command...")
        log.warning("This requires following the on-screen link and authenticating.")

        try:
            # Run interactively to allow terminal I/O for URL and authentication.
            exec_obj.run(["tailscale", "up"], force_sudo=True, interactive=True)
            # If 'up' succeeds, the loop will run the status check again, and it should succeed on the next iteration.
            
        except subprocess.CalledProcessError as e:
            log.error(f"Tailscale 'up' failed with exit code {e.returncode}. You may need to run it manually.")
        except Exception as e:
            log.error(f"Tailscale 'up' failed unexpectedly: {e}")
            
        if attempt < MAX_RETRIES - 1:
            log.info("Waiting 5 seconds before re-checking connection...")
            time.sleep(5)
            
    # If the loop finishes without a successful connection
    log.error(f"Tailscale login failed after {MAX_RETRIES} attempts.")
    return False