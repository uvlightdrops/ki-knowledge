"""Rudimentary network feedback: one log file with node-to-node connections only.

Logs peer origin, method/path, status, duration and error class. Never secrets,
headers, query strings or payloads. Logging failures never propagate.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

LOGGER_NAME = "ki_knowledge.node_network"
ENV_PATH = "KI_NODE_NETLOG"
_lock = Lock()
_state: dict[str, object] = {"path": None, "handler": None}
_last_probe: dict[str, str] = {}


def log_path() -> Path:
    override = os.environ.get(ENV_PATH, "").strip()
    if override:
        return Path(override)
    from ki_knowledge.app_config import AppConfig
    from ki_knowledge.data_layout import DataLayout

    return DataLayout.from_config(AppConfig.from_env()).node_network_log_path()


def _logger() -> logging.Logger | None:
    path = log_path()
    with _lock:
        logger = logging.getLogger(LOGGER_NAME)
        if _state["path"] != path:
            old = _state["handler"]
            if old is not None:
                logger.removeHandler(old)  # type: ignore[arg-type]
                old.close()  # type: ignore[attr-defined]
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
            _state["path"], _state["handler"] = path, handler
        return logger


def _safe_origin(url: str) -> str:
    try:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")
    except ValueError:
        return "invalid-url"


def log_event(direction: str, peer: str, method: str, path: str, outcome: str,
              duration_ms: int | None = None, operation_id: str = "") -> None:
    try:
        parts = [direction, _safe_origin(peer) if "//" in peer else peer, method, path, outcome]
        if duration_ms is not None:
            parts.append(f"{duration_ms}ms")
        if operation_id:
            parts.append(f"op={operation_id}")
        logger = _logger()
        if logger is not None:
            logger.info(" ".join(parts))
    except Exception:  # noqa: BLE001 - feedback must never break a request
        pass


def log_probe(peer: str, status: str, error: str, rtt_ms: int | None) -> None:
    """Header probes run every 30 s: log only state changes."""
    state = f"{status}:{error}"
    if _last_probe.get(peer) == state:
        return
    _last_probe[peer] = state
    log_event("probe", peer, "GET", "/knowledge/sync/node/", error or status, rtt_ms)
