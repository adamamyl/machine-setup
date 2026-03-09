"""
brew_tools.py
=============
Homebrew package-management helpers for macOS (and Linuxbrew, if ever needed).

Design notes
------------
* Homebrew explicitly refuses to run as root.  All functions accept a
  ``brew_user`` argument and execute brew as that user via the Executor's
  ``user=`` mechanism.
* Use ``get_brew_user()`` from ``lib.platform_utils`` to obtain the correct
  user before calling anything here.
* ``find_brew()`` checks PATH first, then the canonical Apple-Silicon and
  Intel install locations, so it works correctly even when called as root
  (where PATH may not include Homebrew's prefix).
"""

import os
import shutil
from typing import Optional

from ..executor import Executor
from ..logger import log

# Ordered by likelihood: Apple Silicon first, then Intel, then Linuxbrew.
_BREW_CANDIDATE_PATHS: list[str] = [
    "/opt/homebrew/bin/brew",           # Apple Silicon (M-series)
    "/usr/local/bin/brew",              # Intel Mac
    "/home/linuxbrew/.linuxbrew/bin/brew",  # Linuxbrew (rarely used here)
]


def find_brew() -> Optional[str]:
    """
    Return the absolute path to the ``brew`` binary, or ``None`` if Homebrew
    is not installed.  Checks ``PATH`` first, then known install locations.
    """
    in_path = shutil.which("brew")
    if in_path:
        return in_path
    for candidate in _BREW_CANDIDATE_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def ensure_brew_installed(exec_obj: Executor, brew_user: str) -> str:
    """
    Ensure Homebrew is installed.  If not found, runs the official install
    script interactively as *brew_user*.

    Returns the path to the ``brew`` binary.
    Raises ``RuntimeError`` if installation fails.
    """
    existing = find_brew()
    if existing:
        log.success(f"Homebrew found at {existing}.")
        return existing

    log.info("Homebrew not found — installing via official script…")
    exec_obj.run(
        'curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash',
        user=brew_user,
        interactive=True,
    )

    installed = find_brew()
    if not installed:
        raise RuntimeError(
            "Homebrew installation completed but 'brew' binary still not found.  "
            "You may need to add Homebrew to PATH manually."
        )
    log.success(f"Homebrew installed at {installed}.")
    return installed


def brew_install(exec_obj: Executor, brew_user: str, *packages: str) -> None:
    """
    Install one or more Homebrew formulae (idempotent).

    Checks ``brew list --formula`` for each package before attempting to
    install, so re-running is safe and fast.
    """
    brew = find_brew()
    if not brew:
        raise FileNotFoundError(
            "Homebrew not found.  Run ensure_brew_installed() first."
        )

    to_install: list[str] = []
    for pkg in packages:
        try:
            result = exec_obj.run(
                [brew, "list", "--formula", pkg],
                user=brew_user,
                check=False,
                run_quiet=True,
            )
            if result.returncode == 0:
                log.success(f"Brew formula already installed: {pkg}")
            else:
                to_install.append(pkg)
        except Exception:
            to_install.append(pkg)

    if not to_install:
        return

    log.info(f"Installing brew formulae: {', '.join(to_install)} …")
    exec_obj.run([brew, "install"] + to_install, user=brew_user)
    log.success(f"Installed via brew: {', '.join(to_install)}")


def brew_service_start(exec_obj: Executor, brew_user: str, service: str) -> None:
    """
    Start *service* via ``brew services start`` (registers with launchd).
    Idempotent — if already running, brew will report that and exit 0.
    """
    brew = find_brew()
    if not brew:
        raise FileNotFoundError("Homebrew not found.")

    log.info(f"Starting brew service: {service} …")
    exec_obj.run([brew, "services", "start", service], user=brew_user)
    log.success(f"Brew service '{service}' started (launchd registered).")


def is_brew_service_running(exec_obj: Executor, brew_user: str, service: str) -> bool:
    """
    Return ``True`` if *service* is currently in the 'started' state according
    to ``brew services info``.
    """
    brew = find_brew()
    if not brew:
        return False
    try:
        result = exec_obj.run(
            [brew, "services", "info", service, "--json"],
            user=brew_user,
            check=False,
            run_quiet=True,
        )
        return result.returncode == 0 and '"started"' in result.stdout
    except Exception:
        return False
