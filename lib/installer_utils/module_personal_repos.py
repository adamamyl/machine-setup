from __future__ import annotations

from pathlib import Path

from ..constants import PERSONAL_GITHUB_REPOS
from ..executor import Executor
from ..logger import log
from .git_tools import clone_or_update_repo

PERSONAL_REPOS_USER: str = "adam"


def _setup_repo(exec_obj: Executor, key: str) -> None:
    url = PERSONAL_GITHUB_REPOS[key]
    user_home = Path(f"~{PERSONAL_REPOS_USER}").expanduser()
    projects_dir = user_home / "projects"
    dest = str(projects_dir / key)

    exec_obj.run(f"mkdir -p {projects_dir}", force_sudo=True)
    exec_obj.run(
        f"chown {PERSONAL_REPOS_USER}:{PERSONAL_REPOS_USER} {projects_dir}", force_sudo=True
    )

    log.info(f"Cloning/updating {key}...")
    clone_or_update_repo(exec_obj, url, dest, user=PERSONAL_REPOS_USER)
    exec_obj.run(f"chown -R {PERSONAL_REPOS_USER}:{PERSONAL_REPOS_USER} {dest}", force_sudo=True)
    log.success(f"{key} ready at {dest}.")


def setup_traefik_proxy(exec_obj: Executor) -> None:
    _setup_repo(exec_obj, "traefik-proxy")


def setup_dracula(exec_obj: Executor) -> None:
    _setup_repo(exec_obj, "dracula")


def setup_docker_dns_reso(exec_obj: Executor) -> None:
    _setup_repo(exec_obj, "docker-dns-reso")


def setup_all_personal_repos(exec_obj: Executor) -> None:
    for key in PERSONAL_GITHUB_REPOS:
        _setup_repo(exec_obj, key)
