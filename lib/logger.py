import logging
import sys
from typing import Any

# --- ANSI Color Codes ---
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
CYAN = "\033[0;36m"
RESET = "\033[0m"
BOLD = "\033[1m"

# --- Emoji Prefixes ---
EMOJI_OK = "✅"
EMOJI_INFO = "ℹ️"
EMOJI_WARN = "⚠️"
EMOJI_ERR = "❌"
EMOJI_DEBUG = "🔎"
EMOJI_PACKAGE = "📦"

SUCCESS = 25
logging.addLevelName(SUCCESS, 'SUCCESS')


class CustomFormatter(logging.Formatter):
    """Custom Formatter that adds colors and emojis based on log level."""
    
    FORMATS = {
        logging.DEBUG: f"{MAGENTA}{EMOJI_DEBUG} DEBUG: {RESET}%(message)s",
        logging.INFO: f"{BOLD}{BLUE}{EMOJI_INFO} {RESET}{BOLD}{BLUE}%(message)s{RESET}",
        SUCCESS: f"{BOLD}{GREEN}{EMOJI_OK} {RESET}{BOLD}{GREEN}%(message)s{RESET}",
        logging.WARNING: f"{BOLD}{YELLOW}{EMOJI_WARN} {RESET}{BOLD}{YELLOW}%(message)s{RESET}",
        logging.ERROR: f"{BOLD}{RED}{EMOJI_ERR} {RESET}{BOLD}{RED}%(message)s{RESET}",
        logging.CRITICAL: f"{BOLD}{RED}{EMOJI_ERR} FATAL: {RESET}{BOLD}{RED}%(message)s{RESET}"
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def configure_logger(quiet: bool = False, verbose: bool = False) -> logging.Logger:
    """Sets up the global logger with custom formatting and handles quiet/verbose flags."""
    
    logger = logging.getLogger("MachineSetup")
    logger.setLevel(logging.DEBUG)

    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CustomFormatter())

    if quiet:
        handler.setLevel(logging.WARNING)
    elif verbose:
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(handler)
    
    def success(msg: str, *args: Any, **kwargs: Any) -> None:
        """Logs a SUCCESS (ok) message."""
        logger.log(SUCCESS, msg, *args, **kwargs)

    setattr(logger, 'success', success)
    
    return logger

def log_module_start(module_name: str, exec_obj: Any) -> None:
    """Logs a formatted banner line to indicate the start of a major module execution."""
    if exec_obj.quiet:
        return
        
    # Define a clean banner line using bold text and blue/cyan colors
    # Example: === 📦 STARTING MODULE: PACKAGES 📦 ===
    
    BANNER_CHAR = "="
    WIDTH = 70 # Increased width for better visibility
    INNER_WIDTH = 60
    
    # 1. Define the core message: 📦 STARTING MODULE: [NAME] 📦
    # The message should use the padding calculated against the INNER_WIDTH.
    msg_content = f" {EMOJI_PACKAGE} STARTING MODULE: {module_name.upper()} {EMOJI_PACKAGE} "
    
    # Use standard string center method for centering the visible text.
    # Python's str.center() handles Unicode width correctly in modern terminals.
    # We pad the content string to the INNER_WIDTH.
    centered_content = msg_content.center(INNER_WIDTH, ' ')
    
    # 2. Construct the outer and inner lines
    outer_line = BANNER_CHAR * WIDTH
    
    # The inner line uses 5 BANNER_CHARs of padding on each side (70 - 60 = 10, / 2 = 5)
    inner_line = f"{BANNER_CHAR * 5}{centered_content}{BANNER_CHAR * 5}"
    
    # Print the result
    print("\n" + outer_line)
    print(f"{BOLD}{CYAN}{inner_line}{RESET}")
    print(outer_line + "\n")

log = logging.getLogger("MachineSetup")