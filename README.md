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


## Ollama

Installs [Ollama](https://ollama.com) locally (bare-metal, for full GPU/CPU access) and deploys [Open WebUI](https://docs.openwebui.com) via Docker Compose. The UI connects to the host Ollama daemon through `host.docker.internal`, so model performance is unaffected by containerisation.

Works on **Linux** and **macOS**.

### Quick start

```bash
# Linux
sudo ./setup_machine.py --ollama

# macOS — no sudo needed (brew refuses to run as root)
./setup_machine.py --ollama
```

Open WebUI will be available at **http://localhost:3000** (or whichever port was free).

### How it installs Ollama

| Platform | Method | Service manager |
| :--- | :--- | :--- |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` | systemd (`systemctl enable ollama --now`) |
| macOS | `brew install ollama` | launchd (`brew services start ollama`) |

Installation is idempotent — re-running skips anything already in place.

### Open WebUI compose stack

The stack is written to `/opt/ollama-webui/` (Linux) or `~/.ollama-webui/` (macOS) and includes:

- `docker-compose.yml` — Open WebUI image, port mapping, volume mounts, env vars
- `.env` — chosen ports and Google PSE credentials (mode `600`, not committed)

Persistent UI data is stored in a named Docker volume (`open-webui-data`).
`~/pseudohome` and `~/projects` are bind-mounted read-only at `/workspace/` inside the container if they exist.
The Docker socket is mounted read-only so the UI can introspect running containers.

### Port selection

Both the Ollama API port (default `11434`) and the WebUI port (default `3000`) are checked for availability before use. If a port is already bound, a free one is selected at random from a configurable range and written to the compose file and `.env`.

### Flags

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--ollama` | — | Run the full Ollama + Open WebUI setup |
| `--ollama-port` | `11434` | Preferred Ollama API port (auto-fallback if taken) |
| `--webui-port` | `3000` | Preferred Open WebUI port (auto-fallback if taken) |
| `--ollama-model` | `ministral:3b` | Model to pull after install |
| `--ollama-user` | `ollama-docker` | System user owning the stack (Linux only) |
| `--ollama-open-path` | — | Add a host path into the compose stack and open a shell |
| `--ollama-terminal` | — | Open a shell in a sibling container with a host path mounted |
| `--ollama-google-api-key` | — | Google PSE API key for web search |
| `--ollama-google-cx` | — | Google PSE engine ID (cx) for web search |

### Accessing a project inside the container

To open an interactive shell in the Open WebUI container with a host directory available at `/workspace/<dirname>`:

```bash
# via the orchestrator
sudo ./setup_machine.py --ollama-terminal ~/projects/machine-setup

# or the standalone helper (no full setup run needed)
./tools/ollama-open-terminal.sh ~/projects/machine-setup
```

This spins up a temporary sibling container sharing the same image and named volume — the primary container is not restarted.

### Google web search (PSE)

Open WebUI can search the web via [Google Programmable Search Engine](https://programmablesearchengine.google.com/). You need two values:

- `GOOGLE_PSE_API_KEY` — a Google Cloud API key with the Custom Search API enabled
- `GOOGLE_PSE_ENGINE_ID` — the `cx` identifier from your PSE

Pass them as flags, or edit `<stack_dir>/.env` after setup:

```bash
# via flags
sudo ./setup_machine.py --ollama \
  --ollama-google-api-key YOUR_KEY \
  --ollama-google-cx YOUR_CX

# or edit the .env directly and restart
#   Linux:  /opt/ollama-webui/.env
#   macOS:  ~/.ollama-webui/.env
docker compose -f <stack_dir>/docker-compose.yml restart
```

Full step-by-step setup instructions (create PSE → enable API → restrict key) are printed to the terminal at the end of every `--ollama` run.

### Example invocations

| Scenario | Command |
| :--- | :--- |
| Defaults (Linux) | `sudo ./setup_machine.py --ollama` |
| Custom model | `sudo ./setup_machine.py --ollama --ollama-model qwen2.5-coder` |
| Custom ports | `sudo ./setup_machine.py --ollama --ollama-port 11435 --webui-port 3001` |
| With web search | `sudo ./setup_machine.py --ollama --ollama-google-api-key KEY --ollama-google-cx CX` |
| macOS, no sudo | `./setup_machine.py --ollama` |
| Open terminal | `./tools/ollama-open-terminal.sh ~/projects/machine-setup` |

---

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

