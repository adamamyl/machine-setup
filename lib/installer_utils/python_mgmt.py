import os
import shutil
import subprocess
from typing import List
from ..executor import Executor
from ..logger import log
from ..constants import VENVDIR, REPO_ROOT
from .apt_tools import apt_install


def install_python_venv(exec_obj: Executor) -> None:
    """Installs Python3, python3-venv, and creates/updates the virtual environment."""
    
    if not os.path.isdir("/opt"):
        log.critical("/opt does not exist. Please create it before running.")
        raise FileNotFoundError("/opt directory missing.")
        
    if not os.access("/opt", os.W_OK):
        log.critical("/opt is not writable. Run as root or adjust permissions.")
        
    python_bin = shutil.which("python3")
    
    if not python_bin or not shutil.which("venv"):
        log.info("Installing Python 3 and venv packages...")
        apt_install(exec_obj, ["python3", "python3-venv", "python3-pip"])
        python_bin = shutil.which("python3")
        if not python_bin:
             log.critical("Failed to install python3. Cannot proceed.")
             raise RuntimeError("Python 3 installation failed.")
    else:
        log.success("Python 3 and venv already installed.")
    
    venv_tool_cmd: List[str]
    venv_tool = shutil.which("uv")
    
    if venv_tool:
        log.info("Using 'uv' for virtual environment management.")
        venv_tool_cmd = [venv_tool, 'venv', VENVDIR]
        install_cmd = [venv_tool, 'pip', 'install', '-r', os.path.join(REPO_ROOT, "requirements.txt")]
    else:
        log.info("Using standard 'python3 -m venv' for virtual environment management.")
        venv_tool_cmd = [python_bin, '-m', 'venv', VENVDIR]
        venv_pip = os.path.join(VENVDIR, "bin", "pip")
        install_cmd = [venv_pip, 'install', '-r', os.path.join(REPO_ROOT, "requirements.txt")]

    if not os.path.isdir(VENVDIR):
        log.info(f"Creating Python virtual environment at {VENVDIR}")
        exec_obj.run(venv_tool_cmd, force_sudo=True)
        
        requirements_file = os.path.join(REPO_ROOT, "requirements.txt")
        if os.path.isfile(requirements_file):
            log.info("Installing Python dependencies from requirements.txt")
            exec_obj.run(install_cmd, force_sudo=True)
        
        log.success(f"Virtual environment created and dependencies installed at {VENVDIR}")
        
    else:
        if not os.access(VENVDIR, os.W_OK):
            log.critical(f"Virtual environment exists at {VENVDIR} but is not writable.")
            raise PermissionError(f"VENVDIR {VENVDIR} not writable.")
        log.success(f"Python virtual environment already exists at {VENVDIR} and is writable.")


def update_readme_with_venv_instructions() -> None:
    """Updates the README.md in the repo root with instructions on activating the VENV."""
    readme_path = os.path.join(REPO_ROOT, "README2.md")
    venv_activate_line = f"To enter the virtual environment, run: `source {VENVDIR}/bin/activate`\n"

    try:
        if os.path.exists(readme_path):
            with open(readme_path, 'r') as f:
                content = f.read()
            
            if venv_activate_line.strip() not in content:
                log.info(f"Adding VENV instructions to {readme_path}")
                with open(readme_path, 'a') as f:
                    f.write("\n## Python Virtual Environment\n")
                    f.write(venv_activate_line)
                    f.write("Run the orchestrator from within the environment after activating.\n")
                log.success("README.md updated with VENV instructions.")
            else:
                log.info("VENV instructions already in README.md.")
        else:
            log.warning(f"README.md not found at {readme_path}. Skipping VENV instructions update.")
    except Exception as e:
        log.error(f"Failed to update README.md: {e}")