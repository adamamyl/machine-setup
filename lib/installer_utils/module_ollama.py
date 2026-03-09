"""
module_ollama.py
================
Installs Ollama locally (as a systemd service) and deploys Open WebUI via
Docker Compose.  Open WebUI connects to the *host* Ollama instance through
``host.docker.internal``, so GPU / CPU resources stay on bare-metal while the
UI runs isolated in a container.

Also provides:
- Port-availability checking with automatic fallback to a random port.
- Permanent bind-mounts for ~/pseudohome and ~/projects inside the container.
- Docker socket pass-through (so the UI can introspect/start containers).
- A helper that lets the user expose *any* validated path into the container
  at run-time (see ``open_terminal_with_path``).
- Google Programmable Search Engine wiring via environment variables.

Usage (from setup_machine.py)
------------------------------
    from lib.installer_utils import module_ollama
    module_ollama.setup_ollama(exec_obj, args)

CLI flags added in setup_machine.py
-------------------------------------
    --ollama                  Run the full Ollama + Open WebUI setup.
    --ollama-port INT         Preferred host port for the Ollama API (default: 11434).
    --webui-port  INT         Preferred host port for Open WebUI     (default: 3000).
    --ollama-model STR        Model to pull after Ollama is installed.
    --ollama-user STR         System user that owns the compose stack.
    --ollama-open-path PATH   Mount a host path read-write into the container and
                              open an interactive bash session there.
    --ollama-google-api-key   GOOGLE_PSE_API_KEY value for web search.
    --ollama-google-cx        GOOGLE_PSE_ENGINE_ID (cx) for web search.
"""

import os
import shutil
import socket
import random
import textwrap
from pathlib import Path
from typing import Optional, List

from ..executor import Executor
from ..logger import log
from ..constants import (
    OLLAMA_STACK_DIR,
    OLLAMA_USER,
    OLLAMA_DEFAULT_PORT,
    WEBUI_DEFAULT_PORT,
    OLLAMA_PORT_SEARCH_MIN,
    OLLAMA_PORT_SEARCH_MAX,
    WEBUI_PORT_SEARCH_MIN,
    WEBUI_PORT_SEARCH_MAX,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_PERMA_MOUNTS,
)
from .user_mgmt import add_user_to_group
from .module_docker import run_docker_compose, are_docker_services_running


# ---------------------------------------------------------------------------
# Port utilities
# ---------------------------------------------------------------------------

def _is_port_free(port: int) -> bool:
    """Return True if *port* is not currently bound on 0.0.0.0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))  # nosec B104 — intentional: probe all-interfaces for true availability
            return True
        except OSError:
            return False


def find_available_port(
    preferred: int,
    search_min: int,
    search_max: int,
    max_attempts: int = 30,
) -> int:
    """
    Return *preferred* if it is free, otherwise pick a random port in
    [search_min, search_max] that is free.  Raises ``RuntimeError`` if no
    free port is found after *max_attempts*.
    """
    if _is_port_free(preferred):
        log.info(f"Port {preferred} is free — using it.")
        return preferred

    log.warning(
        f"Port {preferred} is already in use — searching for a free port "
        f"in [{search_min}, {search_max}]…"
    )
    candidates = list(range(search_min, search_max + 1))
    random.shuffle(candidates)
    for port in candidates[:max_attempts]:
        if _is_port_free(port):
            log.success(f"Selected alternative port: {port}")
            return port

    raise RuntimeError(
        f"Could not find a free port in [{search_min}, {search_max}] "
        f"after {max_attempts} attempts."
    )


# ---------------------------------------------------------------------------
# Ollama local installation
# ---------------------------------------------------------------------------

def install_ollama(exec_obj: Executor) -> None:
    """
    Install Ollama from the official install script (idempotent).
    Enables and starts the systemd service.
    """
    if shutil.which("ollama"):
        log.success("Ollama binary already present — skipping installation.")
        _ensure_ollama_service_running(exec_obj)
        return

    log.info("Installing Ollama via official install script…")
    exec_obj.run(
        "curl -fsSL https://ollama.com/install.sh | sh",
        force_sudo=True,
    )
    log.success("Ollama installed.")

    _ensure_ollama_service_running(exec_obj)


def _ensure_ollama_service_running(exec_obj: Executor) -> None:
    """Enable and start the ollama systemd service if not already running."""
    log.info("Ensuring ollama systemd service is enabled and running…")
    exec_obj.run("systemctl enable ollama --now", force_sudo=True, check=False)

    # Quick health-check
    try:
        result = exec_obj.run(
            "systemctl is-active ollama",
            force_sudo=True,
            check=False,
            run_quiet=True,
        )
        if result.stdout.strip() == "active":
            log.success("Ollama service is active.")
        else:
            log.warning(
                "Ollama service did not report 'active' — it may need a moment "
                "to start.  Check: systemctl status ollama"
            )
    except Exception as exc:
        log.warning(f"Could not verify ollama service status: {exc}")


def pull_ollama_model(exec_obj: Executor, model: str) -> None:
    """
    Pull an Ollama model if not already present.
    Uses ``ollama list`` to check before pulling.
    """
    if not shutil.which("ollama"):
        log.warning("Ollama not found — skipping model pull.")
        return

    log.info(f"Checking whether model '{model}' is already pulled…")
    try:
        result = exec_obj.run(
            ["ollama", "list"],
            check=True,
            run_quiet=True,
            force_sudo=True,
        )
        if model.split(":")[0] in result.stdout:
            log.success(f"Model '{model}' already available — skipping pull.")
            return
    except Exception:
        pass  # If ollama list fails, attempt the pull anyway.

    log.info(f"Pulling Ollama model: {model}  (this may take a while)…")
    # Pull is interactive so the progress bar is visible.
    exec_obj.run(["ollama", "pull", model], force_sudo=True, interactive=True)
    log.success(f"Model '{model}' ready.")


# ---------------------------------------------------------------------------
# Docker Compose stack for Open WebUI
# ---------------------------------------------------------------------------

def _expand_perma_mounts(extra_path: Optional[str] = None) -> List[str]:
    """
    Build the list of bind-mount volume strings for docker-compose.
    ``~/pseudohome`` and ``~/projects`` are always included (if they exist).
    An optional *extra_path* is appended (absolute, validated by the caller).
    """
    home = Path(os.path.expanduser("~"))
    mounts: List[str] = []

    for rel in OLLAMA_PERMA_MOUNTS:
        host_path = home / rel
        if host_path.exists():
            container_path = f"/workspace/{rel}"
            mounts.append(f"{host_path}:{container_path}:ro")
            log.info(f"Perma-mount: {host_path} → {container_path} (ro)")
        else:
            log.warning(
                f"Perma-mount path does not exist and will be skipped: {host_path}"
            )

    if extra_path:
        ep = Path(extra_path).expanduser().resolve()
        container_name = ep.name
        mounts.append(f"{ep}:/workspace/{container_name}:rw")
        log.info(f"Dynamic mount: {ep} → /workspace/{container_name} (rw)")

    return mounts


def _write_compose_file(
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    extra_volumes: List[str],
    google_api_key: str = "",
    google_cx: str = "",
) -> None:
    """Write docker-compose.yml into *stack_dir* (idempotent via force check)."""
    compose_path = os.path.join(stack_dir, "docker-compose.yml")

    # Build the volume lines (indented 6 spaces to match the YAML block)
    vol_lines = [
        "      - open-webui-data:/app/backend/data",
        "      - /var/run/docker.sock:/var/run/docker.sock:ro",
    ]
    for v in extra_volumes:
        vol_lines.append(f"      - {v}")
    volumes_block = "\n".join(vol_lines)

    enable_search = "true" if (google_api_key or google_cx) else "false"

    content = textwrap.dedent(f"""\
        # Auto-generated by machine-setup/module_ollama.py — do not edit by hand.
        # Re-run setup to regenerate.

        services:
          open-webui:
            image: ghcr.io/open-webui/open-webui:main
            container_name: open-webui
            restart: unless-stopped
            ports:
              - "{webui_port}:8080"
            extra_hosts:
              # Lets the container reach the host's Ollama daemon.
              - "host.docker.internal:host-gateway"
            environment:
              - OLLAMA_BASE_URL=http://host.docker.internal:{ollama_port}
              # Web search via Google Programmable Search Engine (PSE).
              # Leave blank to disable; set values in .env or export before
              # running 'docker compose up'.
              - ENABLE_SEARCH_ENGINE_ACCESS={enable_search}
              - GOOGLE_PSE_API_KEY=${{GOOGLE_PSE_API_KEY:-{google_api_key}}}
              - GOOGLE_PSE_ENGINE_ID=${{GOOGLE_PSE_ENGINE_ID:-{google_cx}}}
            volumes:
        {volumes_block}

        volumes:
          open-webui-data:
            name: open-webui-data
    """)

    with open(compose_path, "w") as fh:
        fh.write(content)
    os.chmod(compose_path, 0o644)
    log.success(f"docker-compose.yml written to {compose_path}")


def _write_env_file(
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    google_api_key: str = "",
    google_cx: str = "",
    force: bool = False,
) -> None:
    """Write (or update) the .env file alongside docker-compose.yml."""
    env_path = os.path.join(stack_dir, ".env")

    if os.path.exists(env_path) and not force:
        log.success(f".env already exists at {env_path} — skipping (use --force to overwrite).")
        return

    content = textwrap.dedent(f"""\
        # Auto-generated by machine-setup/module_ollama.py
        # Edit freely — this file is NOT committed to version control.

        WEBUI_PORT={webui_port}
        OLLAMA_PORT={ollama_port}

        # Google Programmable Search Engine — fill in to enable web search in Open WebUI.
        # See research.md / the Google PSE section for setup instructions.
        GOOGLE_PSE_API_KEY={google_api_key}
        GOOGLE_PSE_ENGINE_ID={google_cx}
    """)

    with open(env_path, "w") as fh:
        fh.write(content)
    os.chmod(env_path, 0o600)
    log.success(f".env written to {env_path} (mode 600).")


def setup_open_webui(
    exec_obj: Executor,
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    extra_mount: Optional[str] = None,
    google_api_key: str = "",
    google_cx: str = "",
    force: bool = False,
) -> None:
    """
    Write the docker-compose.yml + .env, then start the Open WebUI stack.
    Idempotent: if the service is already running and *force* is False, skip
    the ``compose up``.
    """
    os.makedirs(stack_dir, exist_ok=True)
    os.chmod(stack_dir, 0o755)  # nosec B103 — system config dir, world-readable is correct

    extra_volumes = _expand_perma_mounts(extra_path=extra_mount)

    # Always (re)write compose so port changes are picked up.
    _write_compose_file(
        stack_dir=stack_dir,
        webui_port=webui_port,
        ollama_port=ollama_port,
        extra_volumes=extra_volumes,
        google_api_key=google_api_key,
        google_cx=google_cx,
    )

    _write_env_file(
        stack_dir=stack_dir,
        webui_port=webui_port,
        ollama_port=ollama_port,
        google_api_key=google_api_key,
        google_cx=google_cx,
        force=force,
    )

    if not force and are_docker_services_running(
        exec_obj, "root", stack_dir, ["open-webui"]
    ):
        log.success("Open WebUI container is already running — skipping 'compose up'.")
        _print_access_info(webui_port)
        return

    log.info("Starting Open WebUI via Docker Compose…")
    # Run compose as root (the stack_dir is owned by root / ollama-docker user).
    run_docker_compose(exec_obj, "root", stack_dir, "up -d --pull always --wait")
    log.success("Open WebUI stack started.")
    _print_access_info(webui_port)


def _print_access_info(webui_port: int) -> None:
    """Print a user-friendly access banner."""
    border = "=" * 60
    print(f"\n{border}")
    print("  🦙 Open WebUI is running!")
    print(f"     URL : http://localhost:{webui_port}")
    print("     Docs: https://docs.openwebui.com")
    print(border)
    print()


# ---------------------------------------------------------------------------
# open-terminal helper — expose a path inside the running container
# ---------------------------------------------------------------------------

def open_terminal_with_path(exec_obj: Executor, host_path: str) -> None:
    """
    Mount *host_path* read-write into the running ``open-webui`` container at
    ``/workspace/<dirname>`` and open an interactive bash session there.

    This does NOT restart or recreate the container — it uses
    ``docker exec`` to open a shell with the path available via a bind-mount
    *in a new temporary container* that shares the same image and volumes.

    Actually, because Docker doesn't support adding mounts to a running
    container, we spin up a *sibling* container from the same image with the
    extra mount and drop into it.  The sibling has access to the same named
    volume (open-webui-data) as well as the requested path.
    """
    ep = Path(host_path).expanduser().resolve()
    if not ep.exists():
        log.error(f"Path does not exist: {ep}")
        raise FileNotFoundError(f"{ep} does not exist")

    container_mount = f"/workspace/{ep.name}"
    log.info(f"Opening terminal in Open WebUI image with {ep} → {container_mount} …")

    cmd = [
        "docker", "run", "--rm", "-it",
        "--name", f"open-webui-terminal-{ep.name}",
        "--network", "host",
        "--add-host", "host.docker.internal:host-gateway",
        "-v", "open-webui-data:/app/backend/data",
        "-v", "/var/run/docker.sock:/var/run/docker.sock:ro",
        "-v", f"{ep}:{container_mount}:rw",
        "-w", container_mount,
        "ghcr.io/open-webui/open-webui:main",
        "bash",
    ]
    exec_obj.run(cmd, force_sudo=True, interactive=True)


# ---------------------------------------------------------------------------
# Google PSE setup instructions
# ---------------------------------------------------------------------------

def print_google_pse_instructions() -> None:
    """Print step-by-step instructions for setting up Google PSE web search."""
    instructions = textwrap.dedent("""\

    ╔══════════════════════════════════════════════════════════════════════╗
    ║         Google Programmable Search Engine (PSE) — Setup Guide       ║
    ╚══════════════════════════════════════════════════════════════════════╝

    Open WebUI can use Google's Programmable Search Engine to give your AI
    assistant the ability to search the web.  You need two credentials:

      1. GOOGLE_PSE_API_KEY   — your Google Cloud API key
      2. GOOGLE_PSE_ENGINE_ID — the "cx" identifier of your search engine

    ── Step 1: Create a Programmable Search Engine ──────────────────────

      a) Go to: https://programmablesearchengine.google.com/
      b) Click "Add" (or "Get started").
      c) Give it a name (e.g. "Open WebUI Search").
      d) Under "What to search", choose "Search the entire web".
      e) Click "Create".
      f) On the next page copy the "Search engine ID" (looks like
         "abc123def456:xyz" or a random alphanumeric string).
         → This is your  GOOGLE_PSE_ENGINE_ID  (also called "cx").

    ── Step 2: Get a Google Cloud API key ───────────────────────────────

      a) Go to: https://console.cloud.google.com/apis/credentials
      b) Click "Create credentials" → "API key".
      c) Copy the generated key.
         → This is your  GOOGLE_PSE_API_KEY.
      d) (Recommended) Restrict the key:
           - Under "API restrictions" choose "Restrict key".
           - Select "Custom Search API".
           - Under "Website restrictions" add your server's IP or domain
             if you want to limit where the key works.

    ── Step 3: Enable the Custom Search API ─────────────────────────────

      a) Go to: https://console.cloud.google.com/apis/library/customsearch.googleapis.com
      b) Click "Enable".

    ── Step 4: Configure Open WebUI ─────────────────────────────────────

    Option A — via .env (recommended, persists across restarts):

      Edit  /opt/ollama-webui/.env  and set:

        GOOGLE_PSE_API_KEY=<your-api-key>
        GOOGLE_PSE_ENGINE_ID=<your-cx>

      Then restart the stack:
        sudo docker compose -f /opt/ollama-webui/docker-compose.yml restart

    Option B — via the Open WebUI admin UI:

      1. Open http://localhost:3000 → Settings (gear icon) → Admin Settings.
      2. Navigate to "Web Search".
      3. Toggle "Enable Web Search".
      4. Set "Web Search Engine" to "google_pse".
      5. Paste your API key and Engine ID.
      6. Save.

    Option C — re-run setup with flags:

      sudo ./setup_machine.py --ollama \\
          --ollama-google-api-key YOUR_KEY \\
          --ollama-google-cx YOUR_CX

    ── Pricing ──────────────────────────────────────────────────────────

      The Custom Search API gives you 100 free queries/day.
      Additional queries cost $5 per 1,000 (up to 10,000/day).
      See: https://developers.google.com/custom-search/v1/overview#pricing

    ── Verification ─────────────────────────────────────────────────────

      In Open WebUI, start a new chat and type a query.  If web search is
      working, you should see a "Searching the web…" indicator and source
      citations in the response.

    ══════════════════════════════════════════════════════════════════════
    """)
    print(instructions)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def setup_ollama(exec_obj: Executor, args) -> None:
    """
    Full Ollama + Open WebUI setup orchestration.

    Steps:
      1. Install Ollama locally (idempotent).
      2. Determine Ollama API port (preferred → free check → fallback).
      3. Determine Open WebUI port (preferred → free check → fallback).
      4. Add the ollama-docker user to the docker group.
      5. Write docker-compose.yml + .env.
      6. Pull requested model.
      7. Start Open WebUI stack.
      8. (Optional) Print Google PSE setup instructions.
    """
    log.info("Starting Ollama + Open WebUI setup…")

    # --- 1. Install Ollama ---
    install_ollama(exec_obj)

    # --- 2. Resolve ports ---
    ollama_port = find_available_port(
        preferred=getattr(args, "ollama_port", OLLAMA_DEFAULT_PORT),
        search_min=OLLAMA_PORT_SEARCH_MIN,
        search_max=OLLAMA_PORT_SEARCH_MAX,
    )
    webui_port = find_available_port(
        preferred=getattr(args, "webui_port", WEBUI_DEFAULT_PORT),
        search_min=WEBUI_PORT_SEARCH_MIN,
        search_max=WEBUI_PORT_SEARCH_MAX,
    )

    # --- 3. Stack directory ---
    stack_dir: str = getattr(args, "ollama_stack_dir", OLLAMA_STACK_DIR)

    # --- 4. Ensure the stack user exists and is in the docker group ---
    ollama_user: str = getattr(args, "ollama_user", OLLAMA_USER)
    try:
        exec_obj.run(
            ["useradd", "-r", "-s", "/usr/sbin/nologin", "-d", stack_dir, ollama_user],
            force_sudo=True,
            check=False,  # Ignore error if user already exists
            run_quiet=True,
        )
    except Exception:
        pass
    add_user_to_group(exec_obj, ollama_user, "docker")

    # --- 5. Open WebUI compose stack ---
    extra_mount: Optional[str] = getattr(args, "ollama_open_path", None)
    google_api_key: str = getattr(args, "ollama_google_api_key", "") or ""
    google_cx: str = getattr(args, "ollama_google_cx", "") or ""

    setup_open_webui(
        exec_obj=exec_obj,
        stack_dir=stack_dir,
        webui_port=webui_port,
        ollama_port=ollama_port,
        extra_mount=extra_mount,
        google_api_key=google_api_key,
        google_cx=google_cx,
        force=exec_obj.force,
    )

    # --- 6. Pull default model ---
    model: str = getattr(args, "ollama_model", OLLAMA_DEFAULT_MODEL)
    pull_ollama_model(exec_obj, model)

    # --- 7. Google PSE instructions (always printed; user can ignore if not needed) ---
    print_google_pse_instructions()

    log.success("Ollama + Open WebUI setup complete.")
