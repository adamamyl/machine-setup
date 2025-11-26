import shutil
import os
from ..executor import Executor
from ..logger import log
from .apt_tools import apt_install, ensure_apt_repo

def install_vscode(exec_obj: Executor) -> None:
    """Installs VSCode using the Microsoft APT repository, ensuring idempotency."""
    if shutil.which("code"):
        log.success("VSCode already installed.")
        return

    log.info("Installing VSCode...")
    
    keyrings_dir = "/etc/apt/keyrings"
    gpg_path = os.path.join(keyrings_dir, "microsoft.gpg")
    list_file = "/etc/apt/sources.list.d/vscode.list"

    exec_obj.run(f"mkdir -p {keyrings_dir}", force_sudo=True)
    
    if not os.path.exists(gpg_path):
        log.info("Adding Microsoft GPG key for VSCode.")
        curl_cmd = f"wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee {gpg_path}"
        exec_obj.run(curl_cmd, force_sudo=True)
    else:
        log.info("VSCode GPG key already exists.")
        
    repo_line = f"deb [arch=amd64 signed-by={gpg_path}] https://packages.microsoft.com/repos/code stable main"
    ensure_apt_repo(exec_obj, list_file, repo_line)

    apt_install(exec_obj, ["code"])
    log.success("VSCode installation complete.")