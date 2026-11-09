"""Bundled static resources and host checks for the wiki server."""

from importlib.resources import files
import ipaddress
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit


ASSETS = {
    "/assets/viewer.css": ("viewer.css", "text/css; charset=utf-8"),
    "/assets/workspace.css": ("workspace.css", "text/css; charset=utf-8"),
    "/assets/workspace.js": ("workspace.js", "text/javascript; charset=utf-8"),
    "/assets/graph.css": ("graph.css", "text/css; charset=utf-8"),
    "/assets/graph-header.css": ("graph-header.css", "text/css; charset=utf-8"),
    "/assets/graph.js": ("graph.js", "text/javascript; charset=utf-8"),
    "/assets/attribute-settings.js": ("attribute-settings.js", "text/javascript; charset=utf-8"),
    "/assets/settings.css": ("settings.css", "text/css; charset=utf-8"),
    "/assets/settings.js": ("settings.js", "text/javascript; charset=utf-8"),
}


def asset_text(name: str) -> str:
    return files("ki_knowledge").joinpath("wiki_assets", name).read_text(encoding="utf-8")


def valid_host(handler: BaseHTTPRequestHandler) -> bool:
    """Only accept the numeric destination address (or localhost on loopback)."""
    try:
        host = handler.headers.get("Host", "")
        parsed = urlsplit("http://" + host)
        if (parsed.netloc != host or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password or parsed.port != handler.server.server_port):
            return False
        destination = ipaddress.ip_address(handler.connection.getsockname()[0])
        if parsed.hostname == "localhost":
            return destination.is_loopback
        return ipaddress.ip_address(parsed.hostname) == destination
    except ValueError:
        return False
