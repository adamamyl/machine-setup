"""
module_ollama.py
================
Installs Ollama locally and deploys Open WebUI via Docker Compose.
Open WebUI connects to the *host* Ollama instance through
``host.docker.internal``, so GPU / CPU resources stay on bare-metal while
the UI runs isolated in a container.

Platform support
----------------
* **Linux** — Ollama installed via the official ``curl | sh`` script and
  managed by systemd.  Compose stack runs in ``/opt/ollama-webui`` as root.
* **macOS** — Ollama installed via ``brew install ollama`` and managed by
  launchd (``brew services``).  Compose stack runs in ``~/.ollama-webui``
  as the real (non-root) user.  ``host.docker.internal`` is provided
  natively by Docker Desktop — no ``extra_hosts`` mapping needed.

Key features
------------
- Port-availability checking with automatic fallback to a random port.
- Permanent read-only bind-mounts for ~/pseudohome and ~/projects.
- Docker socket pass-through so the UI can introspect containers.
- Dynamic extra-path mounting (``--ollama-open-path`` / ``--ollama-terminal``).
- Google Programmable Search Engine wiring via environment variables.

Usage (from setup_machine.py)
------------------------------
    from lib.installer_utils import module_ollama
    module_ollama.setup_ollama(exec_obj, args)

CLI flags (see setup_machine.py for full list)
----------------------------------------------
    --ollama                  Full Ollama + Open WebUI install.
    --ollama-port INT         Preferred Ollama API port  (default: 11434).
    --webui-port  INT         Preferred Open WebUI port  (default: 3000).
    --ollama-model STR        Model to pull on first run (default: ministral:3b).
    --ollama-user STR         System user owning the stack (Linux only).
    --ollama-open-path PATH   Extra host path added to compose + open shell.
    --ollama-google-api-key   GOOGLE_PSE_API_KEY for web search.
    --ollama-google-cx        GOOGLE_PSE_ENGINE_ID (cx) for web search.
    --ollama-terminal PATH    Open interactive shell in sibling container.
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
from ..platform_utils import is_mac, is_linux, get_real_user
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
    TOOLS_DIR,
)
from .user_mgmt import add_user_to_group
from .module_docker import run_docker_compose, are_docker_services_running
from .brew_tools import (
    ensure_brew_installed,
    brew_install,
    brew_service_start,
    is_brew_service_running,
)

# Candidate paths for the ollama binary when it may not be in root's PATH.
_OLLAMA_CANDIDATE_PATHS: List[str] = [
    "/opt/homebrew/bin/ollama",  # Apple Silicon (brew)
    "/usr/local/bin/ollama",     # Intel Mac (brew) or Linux
    "/usr/bin/ollama",           # Linux package installs
]


# ---------------------------------------------------------------------------
# Port utilities
# ---------------------------------------------------------------------------

def _is_port_free(port: int) -> bool:
    """Return True if *port* is not currently bound on any interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))  # nosec B104 — intentional probe of all interfaces
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
    Return *preferred* if free, otherwise pick a random port in
    [search_min, search_max].  Raises ``RuntimeError`` after *max_attempts*.
    """
    if _is_port_free(preferred):
        log.info(f"Port {preferred} is free — using it.")
        return preferred

    log.warning(
        f"Port {preferred} is already in use — searching [{search_min}, {search_max}]…"
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
# Ollama binary location
# ---------------------------------------------------------------------------

def _find_ollama_bin() -> Optional[str]:
    """
    Locate the ``ollama`` binary.  Checks PATH first, then well-known
    locations (important when running as root where Homebrew's prefix may
    not be in PATH).
    """
    in_path = shutil.which("ollama")
    if in_path:
        return in_path
    for candidate in _OLLAMA_CANDIDATE_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Ollama installation — platform-specific
# ---------------------------------------------------------------------------

def install_ollama(exec_obj: Executor) -> None:
    """
    Install Ollama (idempotent) and ensure its background service is running.

    * **Linux** — official ``curl | sh`` install script + ``systemctl``.
    * **macOS** — ``brew install ollama`` + ``brew services``.
    """
    if _find_ollama_bin():
        log.success("Ollama binary already present — skipping installation.")
        _ensure_ollama_service_running(exec_obj)
        return

    if is_mac:
        _install_ollama_mac(exec_obj)
    else:
        _install_ollama_linux(exec_obj)

    _ensure_ollama_service_running(exec_obj)


def _install_ollama_linux(exec_obj: Executor) -> None:
    """Install Ollama on Linux via the official install script."""
    log.info("Installing Ollama via official install script…")
    exec_obj.run(
        "curl -fsSL https://ollama.com/install.sh | sh",
        force_sudo=True,
    )
    log.success("Ollama installed.")


def _install_ollama_mac(exec_obj: Executor) -> None:
    """Install Ollama on macOS via Homebrew."""
    brew_user = get_real_user()
    log.info(f"Installing Ollama via Homebrew (running as '{brew_user}')…")
    ensure_brew_installed(exec_obj, brew_user)
    brew_install(exec_obj, brew_user, "ollama")
    log.success("Ollama installed via Homebrew.")


def _ensure_ollama_service_running(exec_obj: Executor) -> None:
    """Start the Ollama background service using the platform-appropriate method."""
    if is_mac:
        _ensure_ollama_service_mac(exec_obj)
    else:
        _ensure_ollama_service_linux(exec_obj)


def _ensure_ollama_service_linux(exec_obj: Executor) -> None:
    """Enable and start the Ollama systemd service on Linux."""
    log.info("Enabling ollama systemd service…")
    exec_obj.run("systemctl enable ollama --now", force_sudo=True, check=False)
    try:
        result = exec_obj.run(
            "systemctl is-active ollama",
            force_sudo=True,
            check=False,
            run_quiet=True,
        )
        if result.stdout.strip() == "active":
            log.success("Ollama systemd service is active.")
        else:
            log.warning(
                "Ollama service did not report 'active' — it may still be starting.  "
                "Check: systemctl status ollama"
            )
    except Exception as exc:
        log.warning(f"Could not verify ollama service status: {exc}")


def _ensure_ollama_service_mac(exec_obj: Executor) -> None:
    """Start the Ollama launchd service via brew services on macOS."""
    brew_user = get_real_user()
    if is_brew_service_running(exec_obj, brew_user, "ollama"):
        log.success("Ollama brew service is already running.")
        return
    brew_service_start(exec_obj, brew_user, "ollama")


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------

def pull_ollama_model(exec_obj: Executor, model: str) -> None:
    """
    Pull an Ollama model if not already present.

    On macOS the binary may live in Homebrew's prefix (not in root's PATH),
    so we use ``_find_ollama_bin()`` rather than relying on ``PATH``.
    Model listing and pulling also run as the real user on macOS.
    """
    ollama_bin = _find_ollama_bin()
    if not ollama_bin:
        log.warning("Ollama binary not found — skipping model pull.")
        return

    # On macOS brew installs; on Linux the service runs as root / system user.
    run_user: Optional[str] = get_real_user() if is_mac else None

    log.info(f"Checking whether model '{model}' is already pulled…")
    try:
        list_result = exec_obj.run(
            [ollama_bin, "list"],
            user=run_user,
            force_sudo=(run_user is None),
            check=True,
            run_quiet=True,
        )
        if model.split(":")[0] in list_result.stdout:
            log.success(f"Model '{model}' already available — skipping pull.")
            return
    except Exception:
        pass  # If 'ollama list' fails, attempt the pull anyway.

    log.info(f"Pulling Ollama model: {model}  (this may take a while)…")
    exec_obj.run(
        [ollama_bin, "pull", model],
        user=run_user,
        force_sudo=(run_user is None),
        interactive=True,
    )
    log.success(f"Model '{model}' ready.")


# ---------------------------------------------------------------------------
# Docker Compose stack for Open WebUI
# ---------------------------------------------------------------------------

def _default_stack_dir() -> str:
    """
    Return the default compose stack directory for the current platform.

    * Linux  → ``/opt/ollama-webui``   (system-wide, created as root)
    * macOS  → ``~/.ollama-webui``     (user-owned, no root required)
    """
    if is_mac:
        real_home = Path(f"~{get_real_user()}").expanduser()
        return str(real_home / ".ollama-webui")
    return OLLAMA_STACK_DIR


def _expand_perma_mounts(real_user: str, extra_path: Optional[str] = None) -> List[str]:
    """
    Build bind-mount volume strings for docker-compose.

    ``~/pseudohome`` and ``~/projects`` are included read-only if they exist
    under *real_user*'s home directory.  An optional *extra_path* is appended
    read-write.
    """
    home = Path(f"~{real_user}").expanduser()
    mounts: List[str] = []

    for rel in OLLAMA_PERMA_MOUNTS:
        host_path = home / rel
        if host_path.exists():
            container_path = f"/workspace/{rel}"
            mounts.append(f"{host_path}:{container_path}:ro")
            log.info(f"Perma-mount: {host_path} → {container_path} (ro)")
        else:
            log.warning(f"Perma-mount path does not exist — skipping: {host_path}")

    if extra_path:
        ep = Path(extra_path).expanduser().resolve()
        mounts.append(f"{ep}:/workspace/{ep.name}:rw")
        log.info(f"Dynamic mount: {ep} → /workspace/{ep.name} (rw)")

    return mounts


def _write_compose_file(
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    extra_volumes: List[str],
    google_api_key: str = "",
    google_cx: str = "",
) -> None:
    """Write (or overwrite) docker-compose.yml in *stack_dir*."""
    compose_path = os.path.join(stack_dir, "docker-compose.yml")

    vol_lines = [
        "      - open-webui-data:/app/backend/data",
        "      - /var/run/docker.sock:/var/run/docker.sock:ro",
    ]
    for v in extra_volumes:
        vol_lines.append(f"      - {v}")
    volumes_block = "\n".join(vol_lines)

    # On Linux we need to teach Docker the host-gateway address.
    # On macOS, Docker Desktop provides host.docker.internal automatically;
    # the extra_hosts entry is kept for compatibility but is effectively a no-op.
    extra_hosts_block = textwrap.dedent("""\
            extra_hosts:
              # Allows the container to reach the host's Ollama daemon.
              # On macOS with Docker Desktop this is provided automatically;
              # on Linux it maps to the docker0 bridge gateway.
              - "host.docker.internal:host-gateway"
    """)

    enable_search = "true" if (google_api_key or google_cx) else "false"

    content = textwrap.dedent(f"""\
        # Auto-generated by machine-setup/module_ollama.py — do not edit by hand.
        # Re-run setup to regenerate, or edit and restart the stack manually.

        services:
          open-webui:
            image: ghcr.io/open-webui/open-webui:main
            container_name: open-webui
            restart: unless-stopped
            ports:
              - "{webui_port}:8080"
        {extra_hosts_block}
            environment:
              - OLLAMA_BASE_URL=http://host.docker.internal:{ollama_port}
              # ── Google Programmable Search Engine ──────────────────────
              # Leave blank to disable.  See research.md for setup guide.
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
    log.success(f"docker-compose.yml written → {compose_path}")


def _write_env_file(
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    google_api_key: str = "",
    google_cx: str = "",
    force: bool = False,
) -> None:
    """Write (or skip) the .env file alongside docker-compose.yml."""
    env_path = os.path.join(stack_dir, ".env")

    if os.path.exists(env_path) and not force:
        log.success(f".env already exists at {env_path} — skipping (--force to overwrite).")
        return

    content = textwrap.dedent(f"""\
        # Auto-generated by machine-setup/module_ollama.py
        # Safe to edit — NOT committed to version control.

        WEBUI_PORT={webui_port}
        OLLAMA_PORT={ollama_port}

        # Google Programmable Search Engine — see research.md for setup instructions.
        GOOGLE_PSE_API_KEY={google_api_key}
        GOOGLE_PSE_ENGINE_ID={google_cx}
    """)

    with open(env_path, "w") as fh:
        fh.write(content)
    os.chmod(env_path, 0o600)
    log.success(f".env written → {env_path}  (mode 600)")


def setup_open_webui(
    exec_obj: Executor,
    stack_dir: str,
    webui_port: int,
    ollama_port: int,
    compose_user: str,
    real_user: str,
    extra_mount: Optional[str] = None,
    google_api_key: str = "",
    google_cx: str = "",
    force: bool = False,
) -> None:
    """
    Write docker-compose.yml + .env, then bring the Open WebUI stack up.

    *compose_user* is the OS user under which ``docker compose`` runs.
    On Linux this is ``"root"``; on macOS it is the real (non-root) user.
    """
    os.makedirs(stack_dir, exist_ok=True)
    os.chmod(stack_dir, 0o755)  # nosec B103 — system/user config dir

    extra_volumes = _expand_perma_mounts(real_user=real_user, extra_path=extra_mount)

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
        exec_obj, compose_user, stack_dir, ["open-webui"]
    ):
        log.success("Open WebUI is already running — skipping 'compose up'.")
        _print_access_info(webui_port)
        return

    log.info("Starting Open WebUI via Docker Compose…")
    run_docker_compose(exec_obj, compose_user, stack_dir, "up -d --pull always --wait")
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
# open-terminal helper — install to PATH + expose any host path in container
# ---------------------------------------------------------------------------

def install_open_terminal_helper(exec_obj: Executor) -> None:
    """
    Install ``ollama-open-terminal`` to ``/usr/local/bin/`` so it is
    available system-wide without a full path.

    Source: ``tools/ollama-open-terminal.sh`` in this repo.
    Destination: ``/usr/local/bin/ollama-open-terminal`` (no ``.sh``).
    Idempotent — skips if the destination is already up-to-date.
    """
    src = os.path.join(TOOLS_DIR, "ollama-open-terminal.sh")
    dst = "/usr/local/bin/ollama-open-terminal"

    if not os.path.isfile(src):
        log.warning(f"Helper script not found at {src} — skipping install.")
        return

    import shutil as _shutil
    _shutil.copy2(src, dst)
    os.chmod(dst, 0o755)  # nosec B103 — intentional: system CLI tool needs a+x
    log.success(f"Installed: {dst}")

def open_terminal_with_path(exec_obj: Executor, host_path: str) -> None:
    """
    Spin up a *sibling* Open WebUI container with *host_path* bind-mounted
    read-write at ``/workspace/<dirname>`` and drop into an interactive shell.

    The sibling shares the ``open-webui-data`` named volume so you can
    inspect/modify persistent app data alongside your project files.

    Platform differences
    --------------------
    * **Linux** — uses ``--network host`` + ``--add-host host.docker.internal:host-gateway``
      so the shell can reach the Ollama daemon on the host.
    * **macOS** — Docker Desktop does not support ``--network host`` and
      provides ``host.docker.internal`` automatically; neither flag is needed.
    """
    ep = Path(host_path).expanduser().resolve()
    if not ep.exists():
        log.error(f"Path does not exist: {ep}")
        raise FileNotFoundError(f"{ep} does not exist")

    container_mount = f"/workspace/{ep.name}"
    log.info(f"Opening terminal: {ep} → {container_mount} …")

    base_cmd = [
        "docker", "run", "--rm", "-it",
        "--name", f"open-webui-terminal-{ep.name}",
        "-v", "open-webui-data:/app/backend/data",
        "-v", "/var/run/docker.sock:/var/run/docker.sock:ro",
        "-v", f"{ep}:{container_mount}:rw",
        "-w", container_mount,
    ]

    if is_linux:
        # host networking + gateway mapping for Linux Docker engine
        network_flags = [
            "--network", "host",
            "--add-host", "host.docker.internal:host-gateway",
        ]
    else:
        # macOS Docker Desktop provides host.docker.internal natively;
        # --network host is not supported on macOS containers.
        network_flags = []

    cmd = base_cmd + network_flags + ["ghcr.io/open-webui/open-webui:main", "bash"]
    exec_obj.run(cmd, force_sudo=is_linux, interactive=True)


# ---------------------------------------------------------------------------
# Google PSE setup instructions
# ---------------------------------------------------------------------------

def print_google_pse_instructions() -> None:
    """Print step-by-step Google PSE web-search setup instructions."""
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
      c) Name it (e.g. "Open WebUI Search").
      d) Under "What to search", choose "Search the entire web".
      e) Click "Create".
      f) Copy the "Search engine ID" shown on the next page.
         → This is your  GOOGLE_PSE_ENGINE_ID  (also called "cx").

    ── Step 2: Get a Google Cloud API key ───────────────────────────────

      a) Go to: https://console.cloud.google.com/apis/credentials
      b) Click "Create credentials" → "API key".
      c) Copy the key.
         → This is your  GOOGLE_PSE_API_KEY.
      d) Recommended: restrict the key to "Custom Search API" only.

    ── Step 3: Enable the Custom Search API ─────────────────────────────

      https://console.cloud.google.com/apis/library/customsearch.googleapis.com
      → Click "Enable".

    ── Step 4: Configure Open WebUI ─────────────────────────────────────

    Option A — via .env (recommended, survives restarts):

      Edit  <stack_dir>/.env  and set:
        GOOGLE_PSE_API_KEY=<your-api-key>
        GOOGLE_PSE_ENGINE_ID=<your-cx>

      Then restart:  docker compose -f <stack_dir>/docker-compose.yml restart

    Option B — via the Open WebUI admin panel:

      Settings → Admin Settings → Web Search
      Toggle "Enable Web Search" → engine: google_pse → paste credentials.

    Option C — re-run setup:

      # Linux
      sudo ./setup_machine.py --ollama \\
           --ollama-google-api-key YOUR_KEY --ollama-google-cx YOUR_CX

      # macOS (no sudo needed)
      ./setup_machine.py --ollama \\
           --ollama-google-api-key YOUR_KEY --ollama-google-cx YOUR_CX

    ── Pricing ──────────────────────────────────────────────────────────

      100 free queries/day.  Extra: $5 per 1,000 (max 10,000/day).
      See: https://developers.google.com/custom-search/v1/overview#pricing

    ══════════════════════════════════════════════════════════════════════
    """)
    print(instructions)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def setup_ollama(exec_obj: Executor, args) -> None:
    """
    Full Ollama + Open WebUI setup.

    Steps
    -----
    1. Install Ollama locally (platform-appropriate method).
    2. Resolve Ollama API port (preferred → free-check → fallback).
    3. Resolve Open WebUI host port.
    4. Linux only: ensure compose stack user exists + is in docker group.
    5. Write docker-compose.yml + .env.
    6. Bring the Open WebUI compose stack up.
    7. Install ``ollama-open-terminal`` to ``/usr/local/bin/``.
    8. Pull the requested model.
    9. Print Google PSE setup guide.
    """
    log.info(f"Starting Ollama + Open WebUI setup ({'macOS' if is_mac else 'Linux'})…")

    real_user = get_real_user()

    # --- 1. Install Ollama ---
    install_ollama(exec_obj)

    # --- 2 & 3. Resolve ports ---
    ollama_port = find_available_port(
        preferred=getattr(args, "ollama_port", None) or OLLAMA_DEFAULT_PORT,
        search_min=OLLAMA_PORT_SEARCH_MIN,
        search_max=OLLAMA_PORT_SEARCH_MAX,
    )
    webui_port = find_available_port(
        preferred=getattr(args, "webui_port", None) or WEBUI_DEFAULT_PORT,
        search_min=WEBUI_PORT_SEARCH_MIN,
        search_max=WEBUI_PORT_SEARCH_MAX,
    )

    # --- 4. Stack directory + compose user ---
    stack_dir: str = getattr(args, "ollama_stack_dir", None) or _default_stack_dir()

    if is_linux:
        compose_user = "root"
        ollama_system_user: str = getattr(args, "ollama_user", None) or OLLAMA_USER
        # Create a minimal system user that owns the stack (errors ignored if exists).
        exec_obj.run(
            ["useradd", "-r", "-s", "/usr/sbin/nologin", "-d", stack_dir, ollama_system_user],
            force_sudo=True,
            check=False,
            run_quiet=True,
        )
        add_user_to_group(exec_obj, ollama_system_user, "docker")
    else:
        # macOS: docker runs under the real user account via Docker Desktop.
        compose_user = real_user
        log.info(f"macOS: compose stack will run as '{compose_user}'.")

    # --- 5 & 6. Write files and bring stack up ---
    extra_mount: Optional[str] = getattr(args, "ollama_open_path", None)
    google_api_key: str = getattr(args, "ollama_google_api_key", None) or ""
    google_cx: str = getattr(args, "ollama_google_cx", None) or ""

    setup_open_webui(
        exec_obj=exec_obj,
        stack_dir=stack_dir,
        webui_port=webui_port,
        ollama_port=ollama_port,
        compose_user=compose_user,
        real_user=real_user,
        extra_mount=extra_mount,
        google_api_key=google_api_key,
        google_cx=google_cx,
        force=exec_obj.force,
    )

    # --- 7. Install open-terminal helper to /usr/local/bin ---
    install_open_terminal_helper(exec_obj)

    # --- 8. Pull model ---
    model: str = getattr(args, "ollama_model", None) or OLLAMA_DEFAULT_MODEL
    pull_ollama_model(exec_obj, model)

    # --- 9. Instructions ---
    print_google_pse_instructions()

    log.success("Ollama + Open WebUI setup complete.")
