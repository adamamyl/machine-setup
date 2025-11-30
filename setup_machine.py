#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List, Dict, Any, Tuple
import subprocess

# Set up the internal module search path for relative imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import core utilities
from lib.constants import *
from lib.logger import configure_logger, log, SUCCESS, log_module_start
from lib.executor import Executor, EXEC, run_function_as_user

# Global default VM user (used for Docker setup and VM module)
DEFAULT_VM_USER: str = "adam"


def require_root() -> None:
    """Check if the script is run as root (UID 0)."""
    if os.geteuid() != 0:
        log.critical("The orchestrator must be run as root. Please use 'sudo'.")
        sys.exit(1)
    log.info("Running as root.")


def parse_args() -> Tuple[argparse.Namespace, List[str]]:
    """Parse command-line arguments and return the parsed namespace and leftover arguments."""
    parser = argparse.ArgumentParser(
        description="Automated machine setup orchestrator.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Internal Command Group (Hidden from main help) ---
    # Used when 'sudo -u user' recursively calls this script
    group_internal = parser.add_argument_group("Internal Commands (Do not use directly)")
    group_internal.add_argument("--run-cmd", type=str, 
                                help=argparse.SUPPRESS)
    group_internal.add_argument("--run-args", type=str, nargs='*', default=[], 
                                help=argparse.SUPPRESS) 
    
    # --- Global Options ---
    group_global = parser.add_argument_group("Global Options")
    group_global.add_argument("--dry-run", action="store_true", help="Log actions without executing.")
    group_global.add_argument("--force", action="store_true", help="Overwrite files / skip prompts.")
    group_global.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug output.")
    group_global.add_argument("-q", "--quiet", action="store_true", help="Minimal output (warnings and errors only).")
    group_global.add_argument("--no-autoremove", action="store_true", help="Skip 'apt autoremove' at the end.")
    group_global.add_argument("--debug", type=int, nargs='?', const=1, default=0,
                              help="Enable debug tracing (1: basic, 2: detailed).")

    # --- Module Options ---
    group_modules = parser.add_argument_group("Module Options")
    group_modules.add_argument("--all", action="store_true", help="Run all tasks.")
    
    # CORE INFRASTRUCTURE (Explicitly selectable)
    group_modules.add_argument("--root-ssh-keys", action="store_true", dest="do_root_ssh_keys",
                               help="Install SSH keys from GitHub for the root user.")
    
    # SYSTEM/USER SETUP
    group_modules.add_argument("--packages", action="store_true", dest="do_packages",
                               help="Install standard packages and update-all-the-packages.")
    group_modules.add_argument("--sudoers", action="store_true", dest="do_sudoers",
                               help="Install /etc/sudoers.d/staff for NOPASSWD on 'staff' group.")
    group_modules.add_argument("--tailscale", action="store_true", dest="do_tailscale",
                               help="Install and configure Tailscale.")
    group_modules.add_argument("--docker", action="store_true", dest="do_docker",
                               help="Install Docker and add users to the docker group.")
    group_modules.add_argument("--cloud-init", action="store_true", dest="do_cloud_init",
                               help="Install system-level repos (post-cloud-init, etc.).")
    
    # PRIVATE REPOS (Requires interactive key setup)
    group_modules.add_argument("--hwga", "--no2id", action="store_true", dest="do_no2id",
                               help="Setup 'no2id-docker' user and private NO2ID (HWGA) repositories.")
    group_modules.add_argument("--pseudohome", "--psuedohome", action="store_true", dest="do_pseudohome",
                               help="Setup 'adam' user and pseudohome repository (private git.amyl.org.uk).")
    
    # --- Fake-LE Module Flag ---
    group_modules.add_argument("--fake-le", action="store_true", dest="do_fake_le",
                               help="Run Docker Compose, Fake-LE cert generation, and orchestration.")
    
    # --- Virtual Machine Options ---
    group_vm = parser.add_argument_group("Virtual Machine Options")
    group_vm.add_argument("--vm", "--virtmachine", action="store_true", dest="do_vm",
                          help="Run UTM/QEMU virtual machine setup (fstab, guests, etc.).")
    group_vm.add_argument("--vm-user", default=DEFAULT_VM_USER, dest="vm_user",
                          help=f"Specify local user for UTM mount (default: {DEFAULT_VM_USER}).")
    group_vm.add_argument("--vm-force", action="store_true", dest="do_vm_force",
                          help="Bypass VM detection and force execution of VM setup steps.")

    # --- fake_le (self-signed tls certs for testing) Options ---
    group_fake_le_flags = parser.add_argument_group("Fake-LE Orchestration Options")
    group_fake_le_flags.add_argument("--fake-le-debug", action="store_true", dest="fake_le_debug", help="Pass --debug to the fake-le installer script.")
    group_fake_le_flags.add_argument("--fake-le-dry-run", action="store_true", dest="fake_le_dry_run", help="Pass --dry-run to the fake-le installer script.")
    group_fake_le_flags.add_argument("--fake-le-force", action="store_true", dest="fake_le_force", help="Pass --force to the fake-le installer script.")
    group_fake_le_flags.add_argument("--fake-le-ca-install", action="store_true", dest="do_fake_le_ca_install", 
                                     help="Run the installer script to add the CA to the system trust store.")

    return parser.parse_known_args()


# --- Main Execution Block ---
def main():
    args, unknown = parse_args()
    
    # Configure logger first based on quiet/verbose/debug flags
    configure_logger(quiet=args.quiet, verbose=args.verbose or args.debug > 0)
    
    if unknown:
        log.error(f"Unknown arguments encountered: {', '.join(unknown)}")
        sys.exit(1)

    # 1. Enforce Root Execution
    require_root()

    # 2. Configure Global Executor Instance
    global EXEC
    EXEC.dry_run = args.dry_run
    EXEC.quiet = args.quiet
    EXEC.verbose = args.verbose
    EXEC.force = args.force # Propagate force flag for idempotency overrides
    
    # 3. Import Modules (required here for internal command lookup and execution)
    from lib.installer_utils import module_docker, module_no2id, module_pseudohome, tailscale, user_mgmt, packages, virtmachine, vscode, tweaks, module_fake_le
    from lib.installer_utils.apt_tools import apt_autoremove

    log.info(f"Configuration: Dry Run={args.dry_run}, Quiet={args.quiet}, Verbose={args.verbose}, Force={args.force}")

    # 4. Internal Command Execution (Handles recursive calls from sudo -u)
    if args.run_cmd:
        log.debug(f"Executing internal command: {args.run_cmd} with args: {args.run_args}")
        try:
            # Functions that expect the executor object
            module_map = {
                "setup_no2id": (module_no2id, 'setup_no2id'),
                "setup_pseudohome": (module_pseudohome, 'setup_pseudohome'),
            }
            
            # HACK: Direct shell execution delegation for run_function_as_user -> run_shell_cmd
            if args.run_cmd == "run_shell_cmd":
                # We expect the full command string to be in args.run_args[0]
                if not args.run_args:
                    log.critical("Internal command 'run_shell_cmd' missing argument.")
                    sys.exit(1)
                log.debug(f"Executing delegated shell command: {args.run_args[0]}")
                EXEC.run(args.run_args[0], check=True, interactive=True)
                
            elif args.run_cmd in module_map:
                module, func_name = module_map[args.run_cmd]
                target_func = getattr(module, func_name)
                # Execute the function with the global executor instance
                target_func(EXEC)
            
            else:
                log.error(f"Internal command function '{args.run_cmd}' not found.")
                sys.exit(1)
            
            sys.exit(0) # Exit successfully after internal command runs
            
        except Exception as e:
            log.error(f"Internal command failed: {args.run_cmd}. Error: {e}")
            sys.exit(1)
            
    # 5. Determine Task List
    tasks = {
        "root_ssh_keys": args.do_root_ssh_keys,
        "packages": args.do_packages,
        "sudoers": args.do_sudoers,
        "tailscale": args.do_tailscale,
        "docker": args.do_docker,
        "cloud_init": args.do_cloud_init,
        "no2id": args.do_no2id,
        "pseudohome": args.do_pseudohome,
        "fake_le": args.do_fake_le,
    }
    
    if args.all:
        for key in tasks:
            tasks[key] = True

    if not any(tasks.values()) and not args.do_vm:
        log.warning("No modules selected. Use --help for options.")
        return
        
    # --- Environment Setup (Unconditional but non-module, relies on external VENV/uv) ---
    # We rely on the user having run 'uv run' or activated the VENV for the orchestrator itself.
    # VENVDIR is passed to user-modules (sudo -u) via run_function_as_user.
    os.environ['VENVDIR'] = VENVDIR
    os.environ['PATH'] = f"{VENVDIR}/bin:{os.environ.get('PATH', '')}"

    # 6. Execute Modules in Order
    
    if tasks["root_ssh_keys"]:
        log_module_start("ROOT SSH KEYS", EXEC)
        user_mgmt.install_root_ssh_keys(EXEC)
        
    if tasks["packages"]:
        log_module_start("PACKAGES", EXEC)
        packages.install_packages(EXEC)
        packages.install_update_all_packages(EXEC)

    if tasks["docker"]:
        log_module_start("DOCKER", EXEC)
        module_docker.install_docker_and_add_users(EXEC, DEFAULT_VM_USER)

    if tasks["cloud_init"]:
        log_module_start("CLOUD-INIT REPOS", EXEC)
        module_no2id.install_system_repos(EXEC)
        
    if tasks["sudoers"]:
        log_module_start("SUDOERS CONFIG", EXEC)
        user_mgmt.setup_sudoers_staff(EXEC)
        
    if tasks["tailscale"]:
        log_module_start("TAILSCALE", EXEC)
        tailscale.install_tailscale(EXEC)
        tailscale.ensure_tailscale_strict(EXEC)

    # Private User Repositories
    if tasks["pseudohome"]:
        log_module_start("PSEUDOHOME SETUP (USER: ADAM)", EXEC)
        run_function_as_user(EXEC, "adam", "setup_pseudohome")

    if tasks["no2id"]:
        log_module_start("NO2ID SETUP (USER: NO2ID-DOCKER)", EXEC)
        run_function_as_user(EXEC, "no2id-docker", "setup_no2id")
    
    # Local CA and TLS certs setup-a-tron
    if tasks["fake_le"]: 
        log_module_start("FAKE-LE ORCHESTRATION", EXEC)
        # Pass the entire 'args' object so the module can read all the new flags
        module_fake_le.setup_fake_le(EXEC, args)

    # 7. VM Setup
    if args.do_vm:
        log_module_start(f"VIRT MACHINE SETUP (USER: {args.vm_user})", EXEC)
        # Pass the specific flag state directly:
        virtmachine.setup_virtmachine(EXEC, args.vm_user, force_detection=args.do_vm_force)
        
    # 8. Ubuntu Desktop Extras
    from lib.platform_utils import is_ubuntu_desktop
    if is_ubuntu_desktop():
        log_module_start("DESKTOP EXTRAS (VSCODE, TWEAKS)", EXEC)
        vscode.install_vscode(EXEC)
        tweaks.install_gnome_tweaks(EXEC)

    # 9. Final Cleanup
    if not args.no_autoremove:
        log_module_start("FINAL CLEANUP (APT AUTOREMOVE)", EXEC)
        apt_autoremove(EXEC)
        
    log.success("All requested tasks completed.")


if __name__ == "__main__":
    main()