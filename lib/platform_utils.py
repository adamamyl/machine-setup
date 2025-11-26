import platform
import os
import shutil
from typing import Tuple, Dict, Any
from .logger import log

OS: str = platform.system().lower()
is_mac: bool = OS == "darwin"
is_linux: bool = OS == "linux"
DISPLAY_VAR: str = os.environ.get("DISPLAY", "")

def get_platform_info() -> Dict[str, Any]:
    """Returns a dictionary containing platform detection results."""
    return {
        "OS": OS,
        "is_mac": is_mac,
        "is_linux": is_linux,
        "is_ubuntu_desktop": is_ubuntu_desktop()
    }

def is_ubuntu_desktop() -> bool:
    """
    Detects if the environment appears to be an Ubuntu desktop (Linux, DISPLAY set, gnome-shell present).
    """
    if not is_linux:
        return False
    
    if not DISPLAY_VAR:
        return False
    
    return shutil.which("gnome-shell") is not None

def platform_info() -> None:
    """Logs the detected platform information."""
    info = get_platform_info()
    log.info(f"OS: {info['OS']}")
    log.info(f"Mac: {info['is_mac']}")
    log.info(f"Linux: {info['is_linux']}")
    log.info(f"Ubuntu Desktop: {'yes' if info['is_ubuntu_desktop'] else 'no'}")