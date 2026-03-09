# Machine-Setup: Deep Research Report

*Generated from thorough codebase analysis — 2026-03-08*

---

## 1. Project Identity

`machine-setup` is a **root-level post-install orchestrator** for Ubuntu (and Ubuntu-derivative) Linux machines. It automates everything that normally happens by hand after a fresh OS install: packages, SSH keys, Docker, Tailscale, private Git repos, TLS certs, and desktop extras. The main entry point is `setup_machine.py`; everything else is a library module imported by it.

Key stats:
- Language: Python 3 (type-annotated throughout)
- Runtime: `uv run` (preferred) or `/opt/setup-venv` virtualenv
- Only third-party dep: `requests>=2.28` (GitHub token validation)
- Must run as **root** (checked at startup via `os.geteuid() != 0`)

---

## 2. Repository Layout

```
machine-setup/
├── setup_machine.py              ← Main CLI / orchestrator
├── requirements.txt              ← requests>=2.28 only
├── cgpt-bundler.sh               ← Dev utility: concatenates all .py → clipboard
├── fix-repo-ssh.py               ← Standalone: fixes core.sshCommand in multiple repos
├── ollama.md                     ← Feature-requirements note (seed for this work)
├── lib/
│   ├── constants.py              ← ALL global config: paths, package lists, repo defs
│   ├── logger.py                 ← Custom colored logger + log_module_start banner
│   ├── executor.py               ← Command execution engine (sudo, dry-run, user switching)
│   ├── platform_utils.py         ← is_ubuntu_desktop() helper
│   └── installer_utils/
│       ├── apt_tools.py          ← apt_install, ensure_apt_repo, apt_autoremove
│       ├── git_tools.py          ← clone/update repos, SSH perms, set_homedir_perms_recursively
│       ├── user_mgmt.py          ← require_user, add_user_to_group, install_mapped_ssh_keys
│       ├── module_docker.py      ← Docker install + run_docker_compose / helpers
│       ├── module_no2id.py       ← NO2ID user + private HWGA repos
│       ├── module_pseudohome.py  ← Adam user + pseudohome private git
│       ├── module_fake_le.py     ← Self-signed TLS certs via Docker Compose
│       ├── tailscale.py          ← Tailscale install + connection management
│       ├── virtmachine.py        ← UTM/QEMU 9p mounts + bindfs ownership
│       ├── vscode.py             ← VS Code (desktop only)
│       ├── tweaks.py             ← GNOME Tweaks (desktop only)
│       ├── packages.py           ← Standard package installation
│       ├── python_mgmt.py        ← Virtualenv creation
│       └── repo_utils.py         ← SSH key gen, .env sync, deploy-key display
└── tools/
    ├── env-generator.py          ← Diceware .env templating tool
    └── github-deploy-key.py      ← GitHub deploy key validator / manual adder
```

---

## 3. Core Architecture

### 3.1 Executor (`lib/executor.py`)

Every shell interaction goes through a single `Executor` instance (`EXEC`). Key signature:

```python
exec_obj.run(
    command,          # str (→ bash -c) or List[str]
    force_sudo=False, # prepend sudo if not root
    cwd=None,         # working directory
    user=None,        # run as this user via sudo -H -u
    env=None,         # extra env vars (merged with os.environ)
    check=True,       # raise on non-zero exit
    run_quiet=False,  # suppress logging
    interactive=False # inherit stdin/stdout (for prompts, tailscale, etc.)
)
```

Dry-run mode short-circuits before `subprocess.run`, logging `[DRY-RUN]` instead. The returned value is always `subprocess.CompletedProcess`, even in dry-run (with empty stdout/stderr).

There is also `run_function_as_user(executor, user, function_name, *args)` which recursively re-invokes `setup_machine.py` as a different user via `sudo -H -u`. This is how root orchestrates user-owned git operations (pseudohome, no2id).

### 3.2 Logger (`lib/logger.py`)

Custom formatter with ANSI colours and emoji prefixes:

| Level | Emoji | Colour |
|-------|-------|--------|
| DEBUG | 🔎 | Magenta |
| INFO | ℹ️ | Cyan bold |
| SUCCESS (25) | ✅ | Green bold |
| WARNING | ⚠️ | Yellow bold |
| ERROR | ❌ | Red bold |
| CRITICAL | ❌ FATAL | Red bold |

`log_module_start(name, exec_obj)` prints a `====` banner at the start of each module. `SUCCESS` is a custom level (25, between INFO and WARNING). The `log` singleton is `logging.getLogger("MachineSetup")`.

### 3.3 Constants (`lib/constants.py`)

The single source of truth for:
- **Paths**: `VENVDIR=/opt/setup-venv`, `ROOT_SRC_CHECKOUT=/usr/local/src`, `REPO_ROOT` (dynamic)
- **Package lists**: `STANDARD_PACKAGES`, `DOCKER_DEPS`, `DOCKER_PKGS`, `VM_PACKAGES`
- **Repo defs**: `SYSTEM_REPOS` (public), `HWGA_REPOS` (private, keyed by repo name)
- **User→GitHub map**: `USER_GITHUB_KEY_MAP` for authorized_keys downloads

New modules should add their constants here.

---

## 4. Module Pattern

All functional modules live in `lib/installer_utils/` and follow this contract:

```python
# module_example.py

# 1. Private helper functions prefixed with _
def _do_something_internal(exec_obj: Executor, ...) -> ...:
    ...

# 2. One or more public entry-point functions
def setup_example(exec_obj: Executor) -> None:
    """Main entry point called by setup_machine.py."""
    log.info("Starting Example setup...")

    # Pattern: check → skip or act (idempotent)
    if shutil.which("example-binary"):
        log.success("Already installed, skipping.")
    else:
        _install_example(exec_obj)

    log.success("Example setup complete.")
```

**Idempotency** is non-negotiable — every action checks state first. Common patterns:
- `shutil.which()` — binary presence
- `os.path.exists()` / `os.path.isfile()` — file/dir presence
- `dpkg -s <package>` — apt package installed
- `id <user>` — user exists
- Volume/group existence queries via docker/groupadd

**Module registration** in `setup_machine.py`:
1. Add argument to `parse_args()` under a suitable group
2. Add entry to `tasks` dict (for `--all` support)
3. Call `log_module_start()` + module function in the execution block

---

## 5. APT Package Management (`apt_tools.py`)

```python
apt_install(exec_obj, ["package1", "package2"])
# → Calls dpkg -s for each, installs only missing ones
# → Runs apt-get update first if any are missing

ensure_apt_repo(exec_obj, "/etc/apt/sources.list.d/foo.list", "deb ...")
# → Idempotent: checks for duplicate lines, writes if needed

apt_autoremove(exec_obj)
# → Runs at the very end of a full run
```

The Docker installation demonstrates the full GPG-key-then-repo-then-package pattern that should be reused for any third-party repo (including Ollama's official apt repo, if needed).

---

## 6. Git / SSH Key Management

**Public repos** → `clone_or_update_repo(exec_obj, url, dest)` (low-level, no key needed)

**Private repos** → `clone_or_update_private_repo_with_key_check(exec_obj, url, dest, ssh_key_path, ...)`:
- On first SSH permission failure: displays the public key, prompts user to add deploy key, waits, retries

Key generation → `_create_if_needed_ssh_key(exec_obj, user, ssh_dir, key_name)`:
- Generates ED25519, comment = `user@hostname/repo-path`
- ALWAYS enforces 600 on private key, 644 on pub, 700 on .ssh dir

Subsequent pulls use `_configure_repo_ssh_key(exec_obj, user, dest_dir, ssh_key_path)` which sets `core.sshCommand` in the local git config.

---

## 7. Docker Patterns (`module_docker.py`)

**Installation**: Removes conflicts → downloads GPG key → adds APT repo → installs suite → `systemctl enable docker --now` → `docker run hello-world` verification.

**Architecture detection**: `platform.machine()` returns `aarch64` on ARM; corrected to `arm64` for the APT repo line.

**Helper functions** (all in `module_docker.py`, used by other modules):
```python
run_docker_compose(exec_obj, user, cwd, command)
# → Prefers "docker compose" over legacy "docker-compose"
# → Runs as specified user in specified directory

check_docker_volume_exists(exec_obj, volume_name) → bool
are_docker_services_running(exec_obj, user, cwd, service_names) → bool
```

---

## 8. Environment / `.env` File Handling

`tools/env-generator.py` reads a `.env-template` file and generates a `.env` alongside it. For each key:
- If a value exists in the current `.env`, it is preserved.
- If missing, a fresh Diceware 5-word password is generated.

Permissions are set to 600. The generator also updates `.gitignore` and `.dockerignore`.

Modules flag dotenv sync in `HWGA_REPOS` with `"dotenv_sync": True`, then `_dotenv_sync_if_needed()` calls the tool.

---

## 9. User Management

```python
require_user(exec_obj, username)         # useradd -m if not exists
add_user_to_group(exec_obj, user, group) # usermod -aG
create_if_needed_ssh_dir(exec_obj, user) # mkdir ~/.ssh + chmod 700
users_to_groups_if_needed(exec_obj, user, [groups])  # batch

install_mapped_ssh_keys(exec_obj, user, github_account)
# → Fetches https://github.com/{account}.keys
# → Deduplicates and appends to ~/.ssh/authorized_keys
```

---

## 10. Styling Conventions

| Convention | Usage |
|-----------|-------|
| `UPPER_CASE` | Module-level constants |
| `snake_case` | Functions and variables |
| `_leading_underscore` | Private/internal functions |
| Type hints | Everywhere (`Optional[str]`, `List[str]`, `Union[str, List[str]]`) |
| Docstrings | Every public function |
| `log.info` → `log.success` | Start/end of every significant action |
| `check=False` | Only when failure is acceptable/expected |
| `run_quiet=True` | For status-check commands whose output isn't logged |
| `interactive=True` | For any command needing stdin (tailscale up, deploy key prompts) |
| `force_sudo=True` | When running commands that need root but may not be root |

---

## 11. Port Management

**Does not exist yet** in the current codebase. The new Ollama module introduces this. The pattern: try the preferred port with `socket.bind()`; on failure, pick a random port from a safe range and retry until one binds; test it; persist the chosen port to the `.env` file.

---

## 12. `setup_machine.py` Entry Point Structure

```python
# 1. require_root()
# 2. parse_args() → argparse.Namespace
# 3. configure_logger(quiet, verbose)
# 4. EXEC = Executor(dry_run, quiet, verbose, force)
# 5. tasks = {name: bool, ...}   # populated from args
# 6. if args.all: enable all tasks
# 7. Execute enabled tasks in order, each preceded by log_module_start()
# 8. Final: apt_autoremove() unless --no-autoremove
```

Adding a new module means:
1. `parser.add_argument("--ollama", ...)` in `parse_args()`
2. `"ollama": args.do_ollama` in `tasks`
3. `if tasks["ollama"]: log_module_start(...); module_ollama.setup_ollama(EXEC, args)` in the execution block
4. Add any sub-flags (ports, models, paths) to a dedicated argument group

---

## 13. Observed Patterns for New Modules

A new module (e.g., Ollama) should:

1. **Start with constants** in `constants.py` — install dir, default ports, default models
2. **Check idempotency early** — `shutil.which("ollama")` before running the install script
3. **Use the Executor for all shell calls** — never `subprocess.run()` directly
4. **Use `log.info` / `log.success` / `log.warning`** consistently
5. **Write generated files (compose, .env) idempotently** — skip if exists and not `exec_obj.force`
6. **Expose sub-flags** for advanced options (ports, models, Google PSE keys)
7. **Add Docker socket access** where needed (pass `/var/run/docker.sock` as a volume)
8. **Document user-facing instructions** in the module itself (via `log.warning` + print banners)

---

## 14. Key Observations and Gotchas

- The project **must run as root** but delegates user-owned operations via `sudo -H -u <user>`.
- `exec_obj.run()` with `user=` ALWAYS prepends `sudo -H -u`, even when already root.
- `force_sudo=True` is only needed when NOT already root (the `_should_sudo` method checks `os.geteuid()`).
- APT operations always need `force_sudo=True` (or the script IS root, same effect).
- Docker group membership only takes effect on next login; modules that run docker compose do so as the owning user, not the newly-added one.
- The `are_docker_services_running` check uses `{{.Service}} {{.State}}` format — service names must match compose service names exactly.
- `run_docker_compose` splits the `command` string with `.split()`, so commands with quoted arguments need to be passed as a list instead.
- `GIT_BIN_PATH` is determined at import time; if git isn't installed yet when constants.py is imported, it falls back to `/usr/bin/git`.
- Currently, it's very debian/ubuntu focussed, but support for MacOS (and homebrew) should be added as needed; with some clever logic based on `uname` to determine if using `apt` or `brew`. (and determining the path of brew, if on intel or silicon mac)