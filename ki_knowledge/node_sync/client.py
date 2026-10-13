from __future__ import annotations

from typing import Any

import time

import requests

from .netlog import log_event

SECRET_HEADER = "X-KI-Sync-Secret"
OPERATION_HEADER = "X-KI-Operation-Id"

PATH_NODE = "/knowledge/sync/node/"
PATH_HEARTBEAT = "/knowledge/sync/heartbeat/"
PATH_EXPORT = "/knowledge/sync/export/"
PATH_PULL = "/knowledge/sync/pull/"
PATH_CONTRIBUTE = "/knowledge/sync/contribute/"


class SyncClient:
    """All outgoing ki-knowledge sync requests to one configured origin.

    Uses ``requests`` (not ``ki_node_http``) because existing deployments talk plain
    HTTP inside the LAN; errors stay ``requests`` exceptions / ``ValueError`` so the
    callers' unreachable handling is unchanged. No retries: the caller owns
    operation ids and retry budgets.
    """

    def __init__(self, origin: str, *, secret: str = "", timeout: float = 30) -> None:
        origin = (origin or "").strip().rstrip("/")
        if not origin:
            raise ValueError("sync origin not configured")
        self.origin = origin
        self.timeout = max(float(timeout), 5.0)
        self._secret = (secret or "").strip()

    def url(self, path: str) -> str:
        return self.origin + path

    def _headers(self, operation_id: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._secret:
            headers[SECRET_HEADER] = self._secret
        if operation_id:
            headers[OPERATION_HEADER] = operation_id
        return headers

    def _send(self, method: str, path: str, operation_id: str = "", **kwargs: Any) -> requests.Response:
        started = time.monotonic()
        outcome = "error"
        try:
            response = requests.request(method, self.url(path), timeout=self.timeout, **kwargs)
            outcome = str(response.status_code)
            return response
        except requests.exceptions.Timeout:
            outcome = "timeout"
            raise
        except requests.exceptions.ConnectionError:
            outcome = "connection_failed"
            raise
        except requests.exceptions.RequestException as exc:
            outcome = type(exc).__name__
            raise
        finally:
            log_event("out", self.origin, method, path, outcome,
                      round((time.monotonic() - started) * 1000), operation_id)

    @staticmethod
    def _object(response: requests.Response, what: str) -> dict[str, Any]:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"{what} must be an object")
        return payload

    def describe(self) -> dict[str, Any]:
        response = self._send("GET", PATH_NODE, headers=self._headers())
        return self._object(response, "node description")

    def heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._send("POST", PATH_HEARTBEAT, json=payload, headers=self._headers())
        return self._object(response, "heartbeat response")

    def contribute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit an explicit immutable revision; no retry or legacy snapshot push."""
        if not self._secret:
            raise ValueError("contributions require a configured sync secret")
        response = self._send("POST", PATH_CONTRIBUTE, json=payload, headers=self._headers())
        return self._object(response, "contribution response")

    def export(
        self,
        *,
        domains: list[str] | None = None,
        include_projects: bool = True,
        include_documents: bool = True,
        include_knowledge: bool = True,
    ) -> dict[str, Any]:
        params: list[tuple[str, str]] = [
            ("include_projects", "1" if include_projects else "0"),
            ("include_documents", "1" if include_documents else "0"),
            ("include_knowledge", "1" if include_knowledge else "0"),
        ]
        params += [("domain", domain) for domain in normalize_domains(domains)]
        response = self._send("GET", PATH_EXPORT, params=params, headers=self._headers())
        return self._object(response, "master export payload")

    def trigger_pull(self, *, domains: list[str] | None = None, operation_id: str) -> dict[str, Any]:
        """Remote command ``knowledge.domain.pull``: acceptance by the host, not a data push."""
        data = [("domain", domain) for domain in normalize_domains(domains)]
        data.append(("operation_id", operation_id))
        response = self._send("POST", PATH_PULL, operation_id, data=data, headers=self._headers(operation_id))
        return self._object(response, "host pull response")


def normalize_domains(domains: list[str] | None) -> list[str]:
    return [value for value in (str(item).strip() for item in domains or []) if value]
