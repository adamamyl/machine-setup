"""SSH connectivity probe with auto-remediation."""

import os
import pwd
import re
import subprocess
from ..executor import Executor
from ..logger import log

_SAFE_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$")

# Pre-fetched host keys for hosts reachable only via Tailscale.
# Avoids interactive fingerprint prompts during first connection.
# Refresh with: ssh-keyscan <host>
_BAKED_KNOWN_HOSTS: dict[str, list[str]] = {
    "git.amyl.org.uk": [
        "git.amyl.org.uk ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA5p+RFWilkcc9YR5gR2p23mguNrKrtwn3TAgxBOhRDq",
        "git.amyl.org.uk ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBHtSrK7VFPhy2ZsrWjRLcmmeBsTCXPB8IzWz+IE6vkpXuKY91lDdWZdciFZm/RQQilZMxnQwZDfkDK4kGQii7IU=",
    ],
}


def _validate_host(host: str) -> None:
    if not _SAFE_HOSTNAME_RE.match(host):
        raise ValueError(f"Unsafe hostname rejected: {host!r}")


def _user_homedir(ssh_user: str) -> str:
    """Resolve homedir from passwd — portable across /home, /Users, etc."""
    return pwd.getpwnam(ssh_user).pw_dir


def _ssh_probe(
    exec_obj: Executor,
    host: str,
    ssh_user: str,
    key_path: str,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Single SSH test. Returns (auth_ok, stderr)."""
    flags = ["-v"] if verbose else ["-q"]
    cmd = [
        "ssh",
        *flags,
        "-i",
        key_path,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "IdentitiesOnly=yes",
        f"{ssh_user}@{host}",
    ]
    result = exec_obj.run(cmd, user=ssh_user, check=False, run_quiet=True)
    stderr = result.stderr or ""

    if result.returncode == 0:
        return True, stderr
    if result.returncode == 255:
        # SSH protocol-level failure: auth error or network error
        return False, stderr
    # Non-zero but not 255: server rejected interactive shell but auth succeeded
    return True, stderr


def _append_to_known_hosts(ssh_user: str, known_hosts: str, host: str) -> None:
    """Runs ssh-keyscan and appends output to known_hosts directly (runs as root)."""
    try:
        scan = subprocess.run(
            ["ssh-keyscan", "-H", host],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if not scan.stdout.strip():
            log.warning(f"ssh-keyscan returned no output for {host}.")
            return
        # Write directly as root; fix ownership and perms after
        with open(known_hosts, "a") as f:
            f.write(scan.stdout)
        pw = pwd.getpwnam(ssh_user)
        os.chown(known_hosts, pw.pw_uid, pw.pw_gid)
        os.chmod(known_hosts, 0o600)
        log.success(f"Added {host} to {known_hosts}.")
    except Exception as e:
        log.warning(f"ssh-keyscan failed: {e}")


def _seed_known_hosts(ssh_user: str, known_hosts: str, host: str, entries: list[str]) -> None:
    """Writes baked-in known_hosts entries for host if not already present."""
    existing = ""
    if os.path.exists(known_hosts):
        with open(known_hosts) as f:
            existing = f.read()
    new_lines = [e for e in entries if e not in existing]
    if not new_lines:
        return
    with open(known_hosts, "a") as f:
        f.write("\n".join(new_lines) + "\n")
    pw = pwd.getpwnam(ssh_user)
    os.chown(known_hosts, pw.pw_uid, pw.pw_gid)
    os.chmod(known_hosts, 0o600)
    log.info(f"Seeded {len(new_lines)} baked-in host key(s) for {host} into known_hosts.")


def probe_and_fix_ssh(
    exec_obj: Executor,
    host: str,
    ssh_user: str,
    key_path: str,
) -> bool:
    """
    Tests SSH connectivity to host as ssh_user using key_path.
    Auto-remediates where possible (known_hosts, key perms).
    Returns True if SSH is working, False if not (caller should prompt user to add the key).

    Remediations attempted (in order):
      1. Return False on network-level failure (caller will prompt)
      2. ssh-keygen -R to clear any stale host key entry
      3. ssh-keyscan to populate/refresh known_hosts
      4. chmod 700 on .ssh dir and 600 on private key if permissions wrong
      5. Verbose retry with full diagnostics before returning False
    """
    _validate_host(host)
    home = _user_homedir(ssh_user)
    known_hosts = os.path.join(home, ".ssh", "known_hosts")

    # Pre-seed known_hosts with baked-in entries so Tailscale-only hosts don't
    # trigger interactive fingerprint prompts on first connection.
    if host in _BAKED_KNOWN_HOSTS:
        _seed_known_hosts(ssh_user, known_hosts, host, _BAKED_KNOWN_HOSTS[host])

    ok, stderr = _ssh_probe(exec_obj, host, ssh_user, key_path)
    if ok:
        log.success(f"SSH to {ssh_user}@{host}: OK")
        return True

    log.warning(f"SSH to {host} failed — diagnosing...")

    is_network_fail = any(
        x in stderr
        for x in [
            "Connection refused",
            "Connection timed out",
            "No route to host",
            "Network is unreachable",
            "nodename nor servname provided",
        ]
    )
    if is_network_fail:
        log.warning(
            f"Network failure connecting to {host} — key may not be authorised yet.\n"
            f"SSH said: {stderr.strip()}"
        )
        return False

    # Remediation A: clear stale host key unconditionally before re-scanning.
    log.info(f"Clearing any stale known_hosts entry for {host}...")
    exec_obj.run(["ssh-keygen", "-R", host], user=ssh_user, check=False, run_quiet=True)

    # Remediation B: populate/refresh known_hosts (written as root, chowned to user)
    log.info(f"Running ssh-keyscan -H {host}...")
    _append_to_known_hosts(ssh_user, known_hosts, host)

    # Remediation C: fix .ssh dir (700) and private key (600) permissions
    ssh_dir = os.path.dirname(key_path)
    if os.path.isdir(ssh_dir):
        dir_mode = oct(os.stat(ssh_dir).st_mode & 0o777)
        if dir_mode != "0o700":
            log.warning(f"{ssh_dir} has perms {dir_mode}; correcting to 700...")
            exec_obj.run(["chmod", "700", ssh_dir], force_sudo=True)
    if os.path.isfile(key_path):
        key_mode = oct(os.stat(key_path).st_mode & 0o777)
        if key_mode != "0o600":
            log.warning(f"Key {key_path} has perms {key_mode}; correcting to 600...")
            exec_obj.run(["chmod", "600", key_path], force_sudo=True)

    # Retry after remediation
    ok, stderr = _ssh_probe(exec_obj, host, ssh_user, key_path)
    if ok:
        log.success(f"SSH to {ssh_user}@{host}: OK (after remediation)")
        return True

    # Verbose diagnostics
    log.error(f"SSH to {host} still failing. Verbose output:")
    _, verbose_stderr = _ssh_probe(exec_obj, host, ssh_user, key_path, verbose=True)
    for line in verbose_stderr.splitlines():
        log.error(f"  ssh: {line}")

    return False
