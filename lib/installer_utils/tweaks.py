import shutil
from ..executor import Executor
from ..logger import log
from .apt_tools import apt_install
from ..platform_utils import is_ubuntu_desktop

def install_gnome_tweaks(exec_obj: Executor) -> None:
    """Installs GNOME Tweaks if running on Ubuntu Desktop."""
    if shutil.which("gnome-tweaks"):
        log.success("GNOME Tweaks already installed.")
        return
        
    if is_ubuntu_desktop():
        log.info("Installing GNOME Tweaks...")
        apt_install(exec_obj, ["gnome-tweaks"])
        log.success("GNOME Tweaks installed.")
    else:
        log.warning("GNOME Tweaks not installed (not detected as Ubuntu Desktop).")