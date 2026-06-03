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


def _level_filter(logger, method, event_dict):
    """Drop debug/info events when not verbose."""
    if not _verbose:
        level = event_dict.get("level", "info")
        if level in ("debug", "info"):
            raise structlog.DropEvent()
    return event_dict


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

    if _verbose:
        structlog.configure(
            processors=[
                _level_filter,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.dev.ConsoleRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )
    else:
        structlog.configure(
            processors=[
                _level_filter,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
            context_class=dict,
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
