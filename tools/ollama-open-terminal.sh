#!/usr/bin/env bash
# ollama-open-terminal.sh
# ─────────────────────────────────────────────────────────────────────────────
# Open an interactive shell inside a sibling Open WebUI container with a
# host path bind-mounted read-write at /workspace/<dirname>.
#
# The sibling shares the open-webui-data named volume and has Docker socket
# access.  It does NOT restart the primary open-webui container.
#
# Platform notes
# ──────────────
# Linux  : Uses --network host so the shell can reach the Ollama daemon.
#          Adds --add-host host.docker.internal:host-gateway.
# macOS  : Docker Desktop does not support --network host.
#          host.docker.internal is provided automatically — no extra flags.
#
# Usage:
#   ./tools/ollama-open-terminal.sh [HOST_PATH] [OLLAMA_PORT]
#
# Examples:
#   ./tools/ollama-open-terminal.sh ~/projects/machine-setup
#   ./tools/ollama-open-terminal.sh ~/projects/machine-setup 11434
#   sudo ./tools/ollama-open-terminal.sh ~/projects/machine-setup  # Linux
#
# Arguments:
#   HOST_PATH     Absolute or ~-prefixed path on the host to mount.
#                 Defaults to $HOME/projects if omitted.
#   OLLAMA_PORT   Port the host Ollama daemon is listening on (default: 11434).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Detect OS ────────────────────────────────────────────────────────────────
OS="$(uname -s)"

# ── Resolve arguments ────────────────────────────────────────────────────────
HOST_PATH="${1:-${HOME}/projects}"
OLLAMA_PORT="${2:-11434}"

# Expand tilde even when called via sudo (where HOME may be /root)
HOST_PATH="${HOST_PATH/#\~/${HOME}}"
HOST_PATH="$(realpath -e "${HOST_PATH}" 2>/dev/null || echo "")"

if [[ -z "${HOST_PATH}" || ! -e "${HOST_PATH}" ]]; then
    echo "❌  Path does not exist: ${1:-}" >&2
    echo "    Usage: $0 <host-path> [ollama-port]" >&2
    exit 1
fi

CONTAINER_MOUNT="/workspace/$(basename "${HOST_PATH}")"
IMAGE="ghcr.io/open-webui/open-webui:main"
CONTAINER_NAME="open-webui-terminal-$(basename "${HOST_PATH}")-$$"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  🦙 Open WebUI — interactive terminal"
echo "     Host path : ${HOST_PATH}"
echo "     Container : ${CONTAINER_MOUNT}"
echo "     Ollama URL: http://host.docker.internal:${OLLAMA_PORT}"
echo "     Platform  : ${OS}"
echo "══════════════════════════════════════════════════════════"
echo ""

# ── Build the docker run command ─────────────────────────────────────────────
DOCKER_ARGS=(
    run
    --rm
    --interactive
    --tty
    --name "${CONTAINER_NAME}"
    --env "OLLAMA_BASE_URL=http://host.docker.internal:${OLLAMA_PORT}"
    --volume "open-webui-data:/app/backend/data"
    --volume "/var/run/docker.sock:/var/run/docker.sock:ro"
    --volume "${HOST_PATH}:${CONTAINER_MOUNT}:rw"
    --workdir "${CONTAINER_MOUNT}"
)

if [[ "${OS}" == "Linux" ]]; then
    # Linux Docker engine: use host networking and map host.docker.internal
    # to the docker0 bridge gateway so Ollama is reachable from the shell.
    DOCKER_ARGS+=(
        --network host
        --add-host "host.docker.internal:host-gateway"
    )
else
    # macOS Docker Desktop: host.docker.internal resolves automatically.
    # --network host is not supported on macOS; use the default bridge.
    :
fi

DOCKER_ARGS+=("${IMAGE}" bash)

docker "${DOCKER_ARGS[@]}"
