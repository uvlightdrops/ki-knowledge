"""Log inbound node sync requests (peer address, path, status, duration)."""
import time

from ki_knowledge.node_sync.netlog import log_event

SYNC_PREFIX = "/knowledge/sync/"
NODE_PATH = "/knowledge/sync/node/"


class NodeSyncLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(SYNC_PREFIX):
            return self.get_response(request)
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            log_event("in", request.META.get("REMOTE_ADDR", "?"), request.method, request.path, "exception",
                      round((time.monotonic() - started) * 1000))
            raise
        # Peers poll the descriptor every 30 s; keep only failures.
        if not (request.path == NODE_PATH and response.status_code == 200):
            log_event("in", request.META.get("REMOTE_ADDR", "?"), request.method, request.path,
                      str(response.status_code), round((time.monotonic() - started) * 1000),
                      request.headers.get("X-KI-Operation-Id", "")[:64])
        return response
