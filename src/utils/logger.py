# -*- coding: utf-8 -*-
"""Masked logger preventing sensitive API token and key leakage."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler

from src.utils.paths import get_logs_dir

# app.log rolls over at 5 MB and keeps 3 old files (app.log.1 .. app.log.3).
_LOG_MAX_BYTES = 5 * 1024 * 1024
_LOG_BACKUPS = 3

import traceback

_SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"DeepL-Auth-Key\s+\S+", re.IGNORECASE),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?::fx)?\b", re.IGNORECASE),
]
_QUERY_KEY_RE = re.compile(r"([?&](?:api_)?key=)[^&\s\"']+", re.IGNORECASE)
_PROXY_CRED_RE = re.compile(r"((?:https?|socks5h?)://[^/\s:@]+:)[^@\s/]+(@)", re.IGNORECASE)


def mask_secrets(text: str) -> str:
    """Redact API keys, bearer tokens, and proxy credentials from arbitrary text."""
    masked = _PROXY_CRED_RE.sub(r"\1[REDACTED]\2", text)
    masked = _QUERY_KEY_RE.sub(r"\1[REDACTED_API_KEY]", masked)
    for pattern in _SENSITIVE_PATTERNS:
        masked = pattern.sub("[REDACTED_API_KEY]", masked)
    return masked


class SensitiveDataFilter(logging.Filter):
    """Filter that masks API keys and tokens in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._mask_text(record.msg)
        elif record.msg is not None:
            record.msg = self._mask_text(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_item(v) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(self._mask_item(v) for v in record.args)
        if record.exc_info and record.exc_info[0] is not None:
            formatted = "".join(traceback.format_exception(*record.exc_info)).rstrip("\n")
            record.exc_text = self._mask_text(formatted)
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = self._mask_text(record.exc_text)
        return True

    def _mask_text(self, text: str) -> str:
        return mask_secrets(text)

    def _mask_item(self, item: object) -> object:
        if isinstance(item, str):
            return self._mask_text(item)
        if isinstance(item, BaseException):
            return self._mask_text(str(item))
        return item


def setup_logger(name: str = "UnityLocalizer", log_file: str = "app.log") -> logging.Logger:
    """Configure console/file logging for the whole application and return ``name``'s logger.

    Handlers sit on the root logger because every module logs through
    ``logging.getLogger(__name__)`` (``src.core...``), which is not a child of
    ``name``. Application loggers log at DEBUG; third-party libraries only
    reach the handlers from WARNING up, so per-request HTTP chatter stays out.
    """
    logger = logging.getLogger(name)
    root = logging.getLogger()
    for app_logger in (logger, logging.getLogger("src")):
        app_logger.setLevel(logging.DEBUG)
    if any(isinstance(f, SensitiveDataFilter) for h in root.handlers for f in h.filters):
        return logger

    root.setLevel(logging.WARNING)
    log_filter = SensitiveDataFilter()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # A windowed (frozen) build has no stdout; logging to None would raise on every record.
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(log_filter)
        root.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(
            get_logs_dir() / log_file, maxBytes=_LOG_MAX_BYTES, backupCount=_LOG_BACKUPS, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(log_filter)
        root.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Could not create file log: %s", exc)

    return logger
