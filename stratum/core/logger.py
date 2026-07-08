"""Application Logger — Structured logging with rotation and UI integration."""
import logging
import sys
from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class UICallbackHandler(logging.Handler):
    """Logging handler that forwards log records to a UI callback."""

    def __init__(self, callback: Optional[Callable[[str], None]] = None):
        super().__init__()
        self.callback = callback
        self.buffer: List[str] = []

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.buffer.append(msg)
        if self.callback:
            try:
                self.callback(msg)
            except Exception:
                pass

    def set_callback(self, callback: Callable[[str], None]):
        self.callback = callback

    def get_buffer(self, n: int = 100) -> List[str]:
        return self.buffer[-n:]


def setup_logger(name: str = "Stratum", level: int = logging.INFO, log_dir: Optional[str] = None) -> logging.Logger:
    """Configure the application logger."""
    log_path = Path(log_dir or LOG_DIR)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # File handler with rotation
    log_file = log_path / f"stratum_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                       datefmt="%H:%M:%S"))

    # UI handler
    uh = UICallbackHandler()
    uh.setLevel(level)
    uh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                       datefmt="%H:%M:%S"))

    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.addHandler(uh)

    return logger


def get_ui_handler() -> Optional[UICallbackHandler]:
    """Get the UI callback handler from the root logger."""
    logger = logging.getLogger("Stratum")
    for handler in logger.handlers:
        if isinstance(handler, UICallbackHandler):
            return handler
    return None
