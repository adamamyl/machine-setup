from __future__ import annotations

from ..executor import Executor
from ..logger import log
from .git_tools import clone_or_update_repo

WOLFCRAIG_REPO = "/usr/local/src/wolfcraig"
GHOST_DOCKER_REPO = "/usr/local/src/ghost-docker"


def setup_wolfcraig(exec_obj: Executor) -> None:
    """Clone/update wolfcraig and ghost-docker, then run server_setup.py."""

    log.info("Cloning/updating wolfcraig repositories...")
    clone_or_update_repo(
        exec_obj,
        "https://github.com/adamamyl/wolfcraig.git",
        WOLFCRAIG_REPO,
    )
    clone_or_update_repo(
        exec_obj,
        "https://github.com/adamamyl/ghost-docker.git",
        GHOST_DOCKER_REPO,
    )

    cmd = ["uv", "run", "--project", WOLFCRAIG_REPO, "python3", f"{WOLFCRAIG_REPO}/server_setup.py"]
    if exec_obj.dry_run:
        cmd.append("--dry-run")
    if exec_obj.verbose:
        cmd.append("--verbose")
    if exec_obj.force:
        cmd.append("--force")

    log.info("Running wolfcraig server_setup.py...")
    exec_obj.run(cmd, force_sudo=True, check=True)

    log.success("wolfcraig setup complete.")
