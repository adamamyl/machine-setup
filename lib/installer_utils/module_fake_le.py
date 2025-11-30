import os
import sys
import subprocess
from typing import List, Optional 
from ..executor import Executor, run_function_as_user
from ..logger import log
from ..constants import ROOT_SRC_CHECKOUT
from .module_docker import run_docker_compose, check_docker_volume_exists, are_docker_services_running
from pathlib import Path # Required for Python script execution

# Constants specific to this module
NO2ID_USER = "no2id-docker"
HWGA_DIR = f"{ROOT_SRC_CHECKOUT}/herewegoagain"
CERT_GEN_SCRIPT = f"{ROOT_SRC_CHECKOUT}/fake-le/make-local-certs.py" 
CA_INSTALLER_SCRIPT = f"{ROOT_SRC_CHECKOUT}/fake-le/certs-installer.py" 
CERTBOT_VOLUME = "herewegoagain_certbot-etc"
CORE_SERVICES: List[str] = ["wordpress", "mariadb"] 
NGINX_SERVICE_NAME = "nginx" 

# --- New Helper Function to Retrieve CA Path ---

def _get_ca_path_str(exec_obj: Executor) -> Optional[str]:
    """
    Executes the cert generation script with --table-only to ensure CA exists 
    and returns its path.
    """
    log.info(f"Running CA generator script to retrieve CA path...")
    
    try:
        # NOTE: Run as the user who owns the Git repo (no2id-docker)
        # We need to capture stdout, so we must run non-interactively
        
        cmd_list = [
            "python3",
            CERT_GEN_SCRIPT,
            "--table-only"
        ]

        result = exec_obj.run(cmd_list, 
                              user=NO2ID_USER, 
                              check=True, 
                              run_quiet=True)
                              
        # The output contains "CA Root -> /path/to/ca.crt" in the "Full paths:" section
        for line in result.stdout.splitlines():
            if line.startswith("CA Root -> "):
                # Extracts the path string after 'CA Root -> '
                ca_path = line.split(" -> ")[-1].strip() 
                
                # Check if the path ends with ca.crt
                if Path(ca_path).name == 'ca.crt':
                    log.success(f"CA Root path successfully retrieved: {ca_path}")
                    return ca_path
        
        log.error("Could not find 'CA Root -> ' line in script output or path is invalid.")
        return None
        
    except Exception as e:
        log.error(f"Failed to run cert generation script for CA path retrieval: {e}")
        return None

# --- Main setup_fake_le function ---
def setup_fake_le(exec_obj: Executor, args) -> None: # Pass the full args object
    """
    Orchestrates the Docker Compose startup, cert generation, and container restart.
    """
    log.info("Starting **Fake-LE Orchestration**...")
    
    # Check dependencies exist
    if not os.path.isdir(HWGA_DIR):
        log.critical(f"HWGA repository not found at {HWGA_DIR}. Aborting Fake-LE setup.")
        sys.exit(1)
        
    if not Path(CERT_GEN_SCRIPT).is_file(): # Use Path for file check
        log.critical(f"Cert generation script not found at {CERT_GEN_SCRIPT}. Aborting.")
        sys.exit(1)
        
    if args.do_fake_le_ca_install and not Path(CA_INSTALLER_SCRIPT).is_file(): # Use Path for file check
        log.critical(f"CA installer script not found at {CA_INSTALLER_SCRIPT}. Aborting.")
        sys.exit(1)
        
    # Build flags for the CERT_GEN_SCRIPT (these are now command line args for Python)
    cert_gen_flags_list = []
    if args.fake_le_debug:
        cert_gen_flags_list.append("--debug")
    if args.fake_le_dry_run:
        cert_gen_flags_list.append("--dry-run")
    if args.fake_le_force:
        cert_gen_flags_list.append("--force")
    
    # --- 1. Conditional Startup of Docker Compose Services ---
    if are_docker_services_running(exec_obj, NO2ID_USER, HWGA_DIR, CORE_SERVICES):
        log.success("Core Docker services are already running. Skipping 'docker compose up'.")
    else:
        log.info("Core Docker services not found running. Starting Docker Compose services now...")
        try:
            run_docker_compose(exec_obj, NO2ID_USER, HWGA_DIR, "up -d --wait")
            log.success("Docker Compose services started and stable (Nginx may be failing).")
        except Exception as e:
            log.warning(f"Docker Compose failed to start stably. Continuing to check volume.")
            log.debug(f"Docker Compose error: {e}")

    # 2. Check for the volume existence
    if not check_docker_volume_exists(exec_obj, CERTBOT_VOLUME):
        log.critical(f"Required Docker volume '{CERTBOT_VOLUME}' does not exist after startup. Cannot proceed.")
        return

    # 3. Execute the certificate generation script (Python Script Call)
    log.info(f"Executing Certificate Generation script with flags: {' '.join(cert_gen_flags_list)}")
    
    try:
        # The command must be run as the user who owns the cert files (no2id-docker)
        cmd_list = ["python3", CERT_GEN_SCRIPT] + cert_gen_flags_list
        
        # We run this command directly via the executor instance, not recursively
        # This simplifies execution and avoids the run_shell_cmd hack entirely.
        exec_obj.run(cmd_list, user=NO2ID_USER, check=True) 
        
        log.success("Fake-LE certificates successfully generated.")
    except Exception as e:
        log.critical(f"Certificate generation script failed execution. Cannot restart Nginx.")
        log.debug(f"Cert generation error: {e}")
        return

    # --- 4. CA Installer (New Conditional Step) ---
    if args.do_fake_le_ca_install:
        ca_path = _get_ca_path_str(exec_obj)
        if ca_path:
            log.info("Starting CA installation process...")
            
            # NOTE: Installer script is run as root (implicit)
            # The command is: python3 certs-installer.py <ca_path>
            ca_install_cmd = ["python3", CA_INSTALLER_SCRIPT, ca_path]
            
            try:
                # We run this as root because the installer script handles its own sudo inside its main function
                exec_obj.run(ca_install_cmd, check=True, interactive=True)
                log.success("System-wide CA installation complete.")
            except Exception as e:
                log.error(f"CA installation failed. Manual CA trust may be required.")
                log.debug(f"CA install error: {e}")
        else:
            log.warning("Skipping CA installation: Could not retrieve CA path.")

    # 5. Restart the Nginx container
    log.info("Restarting Nginx container to pick up new certificates...")
    try:
        run_docker_compose(exec_obj, NO2ID_USER, HWGA_DIR, f"restart {NGINX_SERVICE_NAME}")
        log.success("Nginx container restarted. Certificates should now be active.")
    except Exception as e:
        log.error(f"Failed to restart Nginx container. Check Docker logs.")
        log.debug(f"Nginx restart error: {e}")
        
    log.success("Fake-LE Orchestration Complete.")