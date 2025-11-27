# machine-setup
machine setup (post-install things)

# UV approach

## 🚀 Running the Orchestrator with `uv run`

The recommended execution method uses **`uv run`** to automatically manage and run the script within an isolated, up-to-date Python environment. This replaces the need to manually `source /opt/setup-venv/bin/activate`.

### Pre-requisites

You must first [install the `uv` binary](https://docs.astral.sh/uv/getting-started/installation/) on your host system and ensure it is available in your PATH (e.g., usually by running the `curl | sh` install script):
 - `curl -LsSf https://astral.sh/uv/install.sh | sh`

### The Base Command

Since your script requires **root privileges** for system changes, you must prepend the command with `sudo`. You need to use `uv run --` to clearly separate `uv`'s flags from the arguments passed to your Python script. Assuming your repository is checked out at `/usr/local/src/machine-setup`:


We do something like this:
```bash
sudo /root/.local/bin/uv run -- python3 /mnt/utm/machine-setup/setup_machine.py --all 
    #local testing, once we've run --vm to mount the mount point
```

or

```bash
# General Syntax:
sudo /root/.local/bin/uv run -- python3 /path/to/script [SCRIPT_FLAGS]

# Specific Invocation Example:
sudo /root/.local/bin/uv run -- python3 /usr/local/src/machine-setup/setup_machine.py --all
```

#### Component Purpose

| Component | Purpose |
| :--- | :--- |
| `sudo` | **Required** for all system modifications (packages, users, fstab). |
| `uv run` | Creates/updates the ephemeral environment and executes the script within it. |
| `--` | **Mandatory** separator telling `uv` that everything after it is the command and arguments for your script. |

## Example command lines
| Scenario | Command | Notes |
| :--- | :--- | :--- |
| **Full Dry Run (Verbose)** | `sudo uv run -- python3 /usr/local/src/machine-setup/setup_machine.py --all --dry-run --verbose` | Essential for testing logic without making changes. |
| **VM Setup (Quiet)** | `sudo uv run -- python3 /usr/local/src/machine-setup/setup_machine.py --vm --vm-user john --quiet` | Installs VM packages/fstab for the user `john`, showing only warnings/errors. |
| **Private Repos Only** | `sudo uv run -- python3 /usr/local/src/machine-setup/setup_machine.py --no2id --pseudohome` | Runs the modules that perform Git clone operations (which include the interactive deploy key step). |
| **Install Docker & Packages**| `sudo uv run -- python3 /usr/local/src/machine-setup/setup_machine.py --docker --packages` | Installs system packages and Docker. |


## Virtual Env approach
🚀 Orchestrator Invocation

1. Activate the Virtual EnvironmentYou must first enter the virtual environment where all Python dependencies are guaranteed to be installed. This should be run as a **regular user**, not root.

```Bash
source /opt/setup-venv/bin/activate
```

Result: Your terminal prompt will change (e.g., to `(setup-venv) $`) indicating the VENV is active.

2. Execute the Setup Script with Options

Once the VENV is active, run the main script using `sudo` to ensure it has the necessary root privileges for system-level changes, packages, and user management.

**The script must be run from the root of your repository** (the directory containing setup_machine.py)

```Bash
sudo ./setup_machine.py --all
```

This command runs all available modules defined in the script (--all).

## Common Invocation Examples
You can combine options depending on what tasks you need to run:

| Scenario | Command |
| :--- | :--- |
| **Full Setup (including dry-run log)** | `sudo ./setup_machine.py --all --dry-run --verbose` |
| **Custom Setup (Docker + NO2ID only)** | `sudo ./setup_machine.py --docker --no2id` |
| **VM Setup for specific user** | `sudo ./setup_machine.py --vm --vm-user john` |
| **Quiet Execution (Errors/Warnings only)** | `sudo ./setup_machine.py --all --quiet` |

