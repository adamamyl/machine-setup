import os
import sys
import subprocess
from typing import List, Optional 
from ..executor import Executor, run_function_as_user
from ..logger import log
from ..constants import ROOT_SRC_CHECKOUT
from .module_docker import run_docker_compose, check_docker_volume_exists, are_docker_services_running

# Constants specific to this module
NO2ID_USER = "no2id-docker"
HWGA_DIR = f"{ROOT_SRC_CHECKOUT}/herewegoagain"
CERT_GEN_SCRIPT = f"{ROOT_SRC_CHECKOUT}/fake-le/fake-le-for-no2id-docker"
CA_INSTALLER_SCRIPT = f"{ROOT_SRC_CHECKOUT}/fake-le/fake-le-for-no2id-docker-installer" 
CERTBOT_VOLUME = "herewegoagain_certbot-etc"
CORE_SERVICES: List[str] = ["wordpress", "mariadb"] 
NGINX_SERVICE_NAME = "nginx" 

# --- Helper Function to Extract CA Path ---
def _get_ca_path(exec_obj: Executor) -> Optional[str]:
    """
    Runs the certificate generation script with --table-only to extract the CA path.
    """
    log.info(f"Running '{CERT_GEN_SCRIPT} --table-only' to retrieve CA path...")
    
    # NOTE: Run as the user who owns the Git repo (no2id-docker)
    try:
        # We need to capture stdout, so we must run non-interactively and suppress logging
        result = exec_obj.run(f"'{CERT_GEN_SCRIPT}' --table-only", 
                              user=NO2ID_USER, 
                              check=True, 
                              run_quiet=True)
                              
        # The output contains "CA Root -> /path/to/ca.crt" in the "Full paths:" section
        for line in result.stdout.splitlines():
            if line.startswith("CA Root -> "):
                ca_path = line.split(" -> ")[-1].strip()
                log.success(f"CA Root path successfully retrieved: {ca_path}")
                return ca_path
        
        log.error("Could not find 'CA Root -> ' line in script output.")
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
        
    if not os.path.exists(CERT_GEN_SCRIPT):
        log.critical(f"Cert generation script not found at {CERT_GEN_SCRIPT}. Aborting.")
        sys.exit(1)
        
    if args.do_fake_le_ca_install and not os.path.exists(CA_INSTALLER_SCRIPT):
        log.critical(f"CA installer script not found at {CA_INSTALLER_SCRIPT}. Aborting.")
        sys.exit(1)
        
    # Build flags for the CERT_GEN_SCRIPT
    cert_gen_flags = []
    if args.fake_le_debug:
        cert_gen_flags.append("--debug")
    if args.fake_le_dry_run:
        cert_gen_flags.append("--dry-run")
    if args.fake_le_force:
        cert_gen_flags.append("--force")
    
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

    # 3. Execute the certificate generation script
    log.info(f"Executing Certificate Generation script with flags: {' '.join(cert_gen_flags)}")
    
    try:
        # Run as the user who owns the repo (no2id-docker)
        cert_gen_cmd = f"'{CERT_GEN_SCRIPT}' {' '.join(cert_gen_flags)}"
        # We use run_function_as_user to delegate execution as NO2ID_USER via the shell hack
        run_function_as_user(exec_obj, NO2ID_USER, "run_shell_cmd", cert_gen_cmd) 
        log.success("Fake-LE certificates successfully generated.")
    except Exception as e:
        log.critical(f"Certificate generation script failed execution. Cannot restart Nginx.")
        log.debug(f"Cert generation error: {e}")
        return

    # --- 4. CA Installer (New Conditional Step) ---
    if args.do_fake_le_ca_install:
        ca_path = _get_ca_path(exec_obj)
        if ca_path:
            log.info("Starting CA installation process...")
            
            # NOTE: CA Installer MUST run as root (exec_obj.run implicitly uses root if not specifying user)
            # The installer script expects the CA path as the first argument
            ca_install_cmd = f"'{CA_INSTALLER_SCRIPT}' '{ca_path}'"
            
            try:
                exec_obj.run(ca_install_cmd, force_sudo=True, check=True)
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