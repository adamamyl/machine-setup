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

log = logging.getLogger("MachineSetup")