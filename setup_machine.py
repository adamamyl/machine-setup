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
from lib.logger import configure_logger, log, SUCCESS
from lib.executor import Executor, EXEC, run_function_as_user

def require_root() -> None:
    """Check if the script is run as root (UID 0)."""
    if os.geteuid() != 0:
        log.critical("The orchestrator must be run as root. Please use 'sudo'.")
        sys.exit(1)
    log.info("Running as root.")


def check_venv() -> None:
    """Checks if the script is running inside the specified virtual environment."""
    current_python = sys.executable
    if VENVDIR not in current_python:
        log.critical("Script is NOT running inside the required virtual environment.")
        log.critical(f"Please run the setup script from the VENV located at: {VENVDIR}")
        log.critical(f"Activate it first: source {VENVDIR}/bin/activate")
        sys.exit(1)
    log.info(f"Running inside VENV: {VENVDIR}")


def parse_args() -> Tuple[argparse.Namespace, List[str]]:
    """Parse command-line arguments and return the parsed namespace and leftover arguments."""
    parser = argparse.ArgumentParser(
        description="Automated machine setup orchestrator.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Internal Command Group (Hidden from main help) ---
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
    group_modules.add_argument("--hwga", "--no2id", action="store_true", dest="do_no2id",
                               help="Setup 'no2id-docker' user and private NO2ID (HWGA) repositories.")
    group_modules.add_argument("--pseudohome", action="store_true", dest="do_pseudohome",
                               help="Setup 'adam' user and pseudohome repository (private git.amyl.org.uk).")
    
    # --- Virtual Machine Options ---
    group_vm = parser.add_argument_group("Virtual Machine Options")
    group_vm.add_argument("--vm", "--virtmachine", action="store_true", dest="do_vm",
                          help="Run UTM/QEMU virtual machine setup (fstab, guests, etc.).")
    group_vm.add_argument("--vm-user", default=DEFAULT_VM_USER, dest="vm_user",
                          help=f"Specify local user for UTM mount (default: {DEFAULT_VM_USER}).")

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
    
    # 3. Import Modules
    from lib.installer_utils import module_docker, module_no2id, tailscale, user_mgmt, packages, virtmachine, python_mgmt
    from lib.installer_utils.apt_tools import apt_autoremove

    log.info(f"Configuration: Dry Run={args.dry_run}, Quiet={args.quiet}, Verbose={args.verbose}")

    # 4. Internal Command Execution (Used when sudo -u <user> calls this script)
    if args.run_cmd:
        log.debug(f"Executing internal command: {args.run_cmd} with args: {args.run_args}")
        try:
            target_func = None
            module_map = {
                "setup_no2id": (module_no2id, 'setup_no2id'),
                "setup_pseudohome": (module_pseudohome, 'setup_pseudohome'),
            }
            
            if args.run_cmd in module_map:
                module, func_name = module_map[args.run_cmd]
                target_func = getattr(module, func_name)
            
            if target_func is None:
                log.error(f"Internal command function '{args.run_cmd}' not found.")
                sys.exit(1)

            # Execute the function with the global executor instance, passing VENVDIR argument
            target_func(EXEC, *args.run_args)
            sys.exit(0)
            
        except Exception as e:
            log.error(f"Internal command failed: {args.run_cmd}. Error: {e}")
            sys.exit(1)
            
    # 5. Mandatory Pre-Flight Setup (Orchestration Phase)
    log.info("Running pre-flight checks and setup...")
    user_mgmt.install_root_ssh_keys(EXEC)
    
    # Python VENV setup must run first to ensure python3 is available for modules
    python_mgmt.install_python_venv(EXEC)
    python_mgmt.update_readme_with_venv_instructions()
    
    # --- VENV Check (AFTER VENV CREATION) ---
    check_venv()
    
    # Propagate VENVDIR globally 
    os.environ['VENVDIR'] = VENVDIR
    os.environ['PATH'] = f"{VENVDIR}/bin:{os.environ['PATH']}"
    
    # 6. Determine Task List
    tasks = {
        "tailscale": args.do_tailscale,
        "packages": args.do_packages,
        "docker": args.do_docker,
        "cloud_init": args.do_cloud_init,
        "sudoers": args.do_sudoers,
        "pseudohome": args.do_pseudohome,
        "no2id": args.do_no2id,
    }
    
    if args.all:
        for key in tasks:
            tasks[key] = True

    if not any(tasks.values()) and not args.do_vm and not args.all:
        log.warning("No modules selected. Use --help for options.")
        return

    # 7. Execute Modules in Order
    if tasks["tailscale"]:
        tailscale.install_tailscale(EXEC)
        tailscale.ensure_tailscale_strict(EXEC)

    if tasks["packages"]:
        packages.install_packages(EXEC)
        packages.install_update_all_packages(EXEC)

    if tasks["docker"]:
        module_docker.install_docker_and_add_users(EXEC, DEFAULT_VM_USER)

    if tasks["cloud_init"]:
        module_no2id.install_system_repos(EXEC)
        
    if tasks["sudoers"]:
        user_mgmt.setup_sudoers_staff(EXEC)

    # Run pseudohome as 'adam' user
    if tasks["pseudohome"]:
        run_function_as_user("adam", "setup_pseudohome", VENVDIR)

    # Run NO2ID (HWGA) as 'no2id-docker' user
    if tasks["no2id"]:
        run_function_as_user("no2id-docker", "setup_no2id", VENVDIR)

    if args.do_vm:
        virtmachine.setup_virtmachine(EXEC, args.vm_user)
        
    # 8. Ubuntu Desktop Extras
    from lib.platform_utils import is_ubuntu_desktop
    from lib.installer_utils import vscode, tweaks
    if is_ubuntu_desktop():
        vscode.install_vscode(EXEC)
        tweaks.install_gnome_tweaks(EXEC)

    # 9. Final Cleanup
    if not args.no_autoremove:
        apt_autoremove(EXEC)
        
    log.success("All requested tasks completed.")


if __name__ == "__main__":
    main()