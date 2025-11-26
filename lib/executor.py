import subprocess
import os
import sys
from typing import List, Optional, Union, Any, Dict
from .logger import log
from . import constants

class Executor:
    """
    Centralized execution engine for all shell commands.
    Handles DRY_RUN, SUDO elevation, logging, and error checking.
    """

    def __init__(self, dry_run: bool = False, quiet: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.quiet = quiet
        self.verbose = verbose

    def _should_sudo(self, force_sudo: bool) -> bool:
        """Determines if 'sudo' needs to be prepended to the command."""
        if not force_sudo:
            return False
        return os.geteuid() != 0

    def run(self, 
            command: Union[str, List[str]], 
            force_sudo: bool = False, 
            cwd: Optional[str] = None, 
            user: Optional[str] = None,
            env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        """
        Executes a shell command.
        """
        
        if isinstance(command, str):
            cmd_list = ['bash', '-c', command]
            log_cmd = command
        else:
            cmd_list = command
            log_cmd = " ".join(command)

        if user:
            if os.geteuid() != 0:
                log_cmd = f"sudo -H -u {user} {log_cmd}"
                cmd_list = ['sudo', '-H', '-u', user] + cmd_list
            else:
                log_cmd = f"(user: {user}) {log_cmd}"
                cmd_list = ['sudo', '-H', '-u', user] + cmd_list
        elif self._should_sudo(force_sudo):
            log_cmd = f"(root) {log_cmd}"
            cmd_list = ['sudo'] + cmd_list
        
        if self.dry_run:
            log.info(f"[DRY-RUN] {log_cmd}")
            return subprocess.CompletedProcess(args=cmd_list, returncode=0, stdout=b"", stderr=b"")

        log.info(f"Executing: {log_cmd}")
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(
                cmd_list,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
                universal_newlines=True
            )
            log.debug(f"Command Output:\n{result.stdout}\n{result.stderr}")
            log.success(f"Executed: {log_cmd}")
            return result
        except subprocess.CalledProcessError as e:
            log.error(f"Command failed with exit code {e.returncode}: {log_cmd}")
            log.error(f"STDOUT:\n{e.stdout}")
            log.error(f"STDERR:\n{e.stderr}")
            raise
        except FileNotFoundError:
            log.critical(f"Command not found: {cmd_list[0]}")
            sys.exit(1)
            
EXEC = Executor()


def run_function_as_user(executor: Executor, 
                         user: str, 
                         function_name: str, 
                         *func_args: str) -> subprocess.CompletedProcess:
    """
    Executes a specific Python function (by name) from the main script as another user
    by recursively calling the setup script with internal arguments.
    """
    
    cmd_list = [
        "python3", 
        os.path.abspath(os.path.join(constants.REPO_ROOT, 'setup_machine.py')), 
        "--run-cmd", 
        function_name
    ]
    cmd_list.extend(func_args)
    
    if executor.dry_run:
        cmd_list.append("--dry-run")
    if executor.quiet:
        cmd_list.append("--quiet")
    if executor.verbose:
        cmd_list.append("--verbose")
    
    log.info(f"Delegating execution to user '{user}' for function: {function_name}")

    return executor.run(cmd_list, user=user)