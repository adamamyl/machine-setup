import os
from typing import Dict, List, Any
import shutil

# --- Global Configuration Paths ---
VENVDIR: str = "/opt/setup-venv"

# Determine the repository root dynamically
REPO_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB_DIR: str = os.path.join(REPO_ROOT, "lib")
TOOLS_DIR: str = os.path.join(REPO_ROOT, "tools")

# --- System Config ---
ROOT_SRC_CHECKOUT: str = "/usr/local/src"
DEFAULT_VM_USER: str = "adam"

# --- Binary Paths ---
# Find the absolute path for git, ensuring portability.
GIT_BIN_PATH: str = shutil.which('git') or '/usr/bin/git' 

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
HWGA_REPOS: Dict[str, Dict[str, Any]] = {
    "herewegoagain": {
        "user": "no2id-docker",
        "url": "git@github.com:no2id/herewegoagain.git",
        "dest": f"{ROOT_SRC_CHECKOUT}/herewegoagain",
        "installer": "install",
        "extra_flags": "--recursive",
        "dotenv_sync": True,
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

# Packages required for Docker (Based on Docker install script pre-reqs: ca-certificates curl)
DOCKER_DEPS: List[str] = ["curl", "gnupg", "lsb-release", "ca-certificates"]

# Full modern Docker suite (Matching successful installation log)
DOCKER_PKGS: List[str] = [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-compose-plugin",
    "docker-buildx-plugin",
    "docker-ce-rootless-extras",
    "docker-model-plugin",
]

# --- Ollama / OpenWebUI Configuration ---

# Directory where the docker-compose stack and .env are written
OLLAMA_STACK_DIR: str = "/opt/ollama-webui"

# The system user that owns the compose stack
OLLAMA_USER: str = "ollama-docker"

# Default Ollama API port (local, on the host)
OLLAMA_DEFAULT_PORT: int = 11434

# Default OpenWebUI port (host side; container always listens on 8080)
WEBUI_DEFAULT_PORT: int = 3000

# Port-search range when the preferred port is already taken
OLLAMA_PORT_SEARCH_MIN: int = 11400
OLLAMA_PORT_SEARCH_MAX: int = 11500
WEBUI_PORT_SEARCH_MIN: int = 3001
WEBUI_PORT_SEARCH_MAX: int = 3099

# Default model to pull after Ollama is installed (lightweight, fast)
OLLAMA_DEFAULT_MODEL: str = "ministral:3b"

# Permanent host paths bind-mounted read-only into the OpenWebUI container.
# These are expanded at runtime relative to the real user's HOME.
OLLAMA_PERMA_MOUNTS: List[str] = [
    "pseudohome",
    "projects",
]

# Firewall module:
FIREWALL_SCRIPT_DEST: str = "/usr/local/bin/apply-firewall.sh"
FIREWALL_SERVICE_NAME: str = "firewall.service"
FIREWALL_CONF_DIR: str = "/etc/iptables"
# iptables and ip6tables are standard, but we ensure iptables-persistent 
# directory structure exists for our own script's logic.
FIREWALL_PACKAGES: List[str] = ["iptables", "curl"]
