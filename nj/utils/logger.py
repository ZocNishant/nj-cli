from __future__ import annotations

import logging
from pathlib import Path

import structlog

_verbose: bool = False


def set_verbose(verbose: bool) -> None:
    global _verbose
    _verbose = verbose


def is_verbose() -> bool:
    return _verbose


def setup_logger(
    level: str = "INFO",
    log_file: str = "logs/nj.log",
    console_level: str = "WARNING",
) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    file_level = getattr(logging, level.upper(), logging.INFO)
    con_level = getattr(logging, console_level.upper(), logging.WARNING)

    root = logging.getLogger()
    root.setLevel(min(file_level, con_level))
    root.handlers.clear()

    # File handler — INFO and above by default
    fh = logging.FileHandler(log_file)
    fh.setLevel(file_level)
    fh.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(fh)

    # Console handler — WARNING and above by default
    ch = logging.StreamHandler()
    ch.setLevel(con_level)
    ch.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(ch)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
