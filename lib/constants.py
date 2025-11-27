import os
from typing import Dict, List

# --- Global Configuration Paths ---
VENVDIR: str = "/opt/setup-venv"

# Determine the repository root dynamically
REPO_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB_DIR: str = os.path.join(REPO_ROOT, "lib")
TOOLS_DIR: str = os.path.join(REPO_ROOT, "tools")

# --- System Config ---
ROOT_SRC_CHECKOUT: str = "/usr/local/src"
DEFAULT_VM_USER: str = "adam"

# --- SSH Key Mappings ---
# Maps local Linux user (key) to GitHub account (value) for authorized_keys download.
# Note: Multiple GitHub accounts can be listed for one local user, separated by spaces.
USER_GITHUB_KEY_MAP: Dict[str, str] = {
    "root": "adamamyl",
    "adam": "adamamyl",
    # Add more users here:
    # "john": "johnsmith123" 
}

# --- Repo/Installer Definitions ---

# System Repos
SYSTEM_REPOS: Dict[str, Dict[str, str]] = {
    "post-cloud-init": {
        "url": "https://github.com/adamamyl/post-cloud-init.git",
        "installer": "install"
    },
    "update-all-the-packages": {
        "url": "https://github.com/adamamyl/update-all-the-packages.git",
        "installer": "install-unattended-upgrades"
    }
}

# NO2ID / Private Repos
HWGA_REPOS: Dict[str, Dict[str, str]] = {
    "herewegoagain": {
        "user": "no2id-docker",
        "url": "git@github.com:no2id/herewegoagain.git",
        "dest": f"{ROOT_SRC_CHECKOUT}/herewegoagain",
        "installer": "install",
        "extra_flags": "--recursive"
    },
    "fake-le": {
        "user": "adam",
        "url": "git@github.com:adamamyl/fake-le.git",
        "dest": f"{ROOT_SRC_CHECKOUT}/fake-le",
        "installer": "fake-le-for-no2id-docker-installer",
        "extra_flags": ""
    }
}

# Standard Packages
STANDARD_PACKAGES: List[str] = [
    "diceware", "findutils", "grep", "gzip", "hostname", "iputils-ping",
    "net-tools", "openssh-server", "vim", "python3", "git", "curl", "mtr", "tree"
]

# Packages required for VM setup
VM_PACKAGES: List[str] = ["spice-vdagent", "qemu-guest-agent", "bindfs"]

# Packages required for Docker
DOCKER_DEPS: List[str] = ["curl", "gnupg", "lsb-release"]
DOCKER_PKGS: List[str] = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-compose-plugin"]
