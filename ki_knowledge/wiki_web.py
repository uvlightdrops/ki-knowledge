"""HTTP integration for the explicitly enabled local workspace."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from html import escape
import json
import secrets
from urllib.parse import parse_qs, quote, urlsplit

from ki_knowledge.wiki_assets import asset_text, valid_host
from ki_knowledge.wiki_relations import RELATION_TYPES
from ki_knowledge.wiki_workspace import Workspace, WorkspaceConflict, WorkspaceError

GRAPH_VIEWS = {"/workspace/graph/": "graph.html", "/workspace/graph-header/": "graph-header.html",
               "/workspace/settings/": "settings.html"}


def make_workspace_handler(base: type[BaseHTTPRequestHandler], workspace: Workspace | None,
                           domains: dict | None = None) -> type[BaseHTTPRequestHandler]:
    token = secrets.token_hex(32)
    domains = domains or {}

    class Handler(base):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path not in {"/workspace/", "/workspace/api", *GRAPH_VIEWS}:
                super().do_GET()
                return
            if not valid_host(self):
                self._json(403, {"error": "Ungültiger Host; bitte die IP-Adresse des Servers verwenden."})
                return
            if path == "/workspace/":
                if workspace is None:
                    self.send_response(303)
                    self.send_header("Location", "/workspace/graph/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                page = (asset_text("workspace.html").replace("__WORKSPACE_TOKEN__", token)
                        .replace("__DJANGO_URL__", escape(self.django_link(), quote=True)).encode("utf-8"))
                self._send(200, page, "text/html; charset=utf-8")
                return
            if path in GRAPH_VIEWS:
                if workspace is None and not parse_qs(urlsplit(self.path).query).get("domain") and domains:
                    self.send_response(303)
                    self.send_header("Location", path + "?domain=" + quote(next(iter(domains)), safe=""))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                options = "".join(
                    f'<label class="relation-type {escape(color, quote=True)}"><input type="radio" '
                    f'name="relation-type" value="{escape(name, quote=True)}"'
                    f'{" checked" if index == 0 else ""}> {escape(name)}</label>'
                    for index, (name, color) in enumerate(RELATION_TYPES)
                )
                domain_links = (f'<a href="{path}">Wiki</a> ' if workspace else "")
                domain_links += " ".join(
                    f'<a href="{path}?domain={quote(name, safe="")}">{escape(name)}</a>'
                    for name in domains
                )
                page = (asset_text(GRAPH_VIEWS[path]).replace("__WORKSPACE_TOKEN__", token)
                        .replace("__DOMAIN_LINKS__", domain_links)
                        .replace("__RELATION_OPTIONS__", options).encode("utf-8"))
                self._send(200, page, "text/html; charset=utf-8")
                return
            try:
                name = parse_qs(urlsplit(self.path).query).get("domain", [""])[0]
                if name:
                    if name not in domains:
                        raise WorkspaceError("Unbekannte Domäne.")
                    self._json(200, domains[name].snapshot())
                elif workspace:
                    self._json(200, {"blocks": workspace.list_blocks(), "errors": []})
                else:
                    raise WorkspaceError("Bitte eine Domäne auswählen.")
            except WorkspaceError as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/workspace/api":
                self._json(404, {"error": "Unbekannter Endpunkt."})
                return
            expected_origin = f"http://{self.headers.get('Host', '')}"
            provided_token = self.headers.get("X-Workspace-Token", "")
            if (not valid_host(self) or self.headers.get("Origin") != expected_origin
                    or not secrets.compare_digest(provided_token, token)):
                self._json(403, {"error": "Anfrage nicht für diesen lokalen Arbeitsraum freigegeben."})
                return
            if self.headers.get_content_type() != "application/json":
                self._json(415, {"error": "JSON wird erwartet."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1024 * 1024:
                    raise WorkspaceError("Anfrage ist leer oder größer als 1 MiB.")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise WorkspaceError("JSON-Objekt wird erwartet.")
                action = payload.get("action")
                name = payload.get("domain", "")
                if name:
                    if not isinstance(name, str) or name not in domains or action != "graph-relate":
                        raise WorkspaceError("Unbekannte Domäne oder Aktion.")
                    block = domains[name].relate(payload)
                elif workspace is None:
                    raise WorkspaceError("Bitte eine Domäne auswählen.")
                elif action == "create":
                    block = workspace.create(payload.get("title"), payload.get("text"))
                else:
                    block = workspace.update(payload.get("id"), payload.get("revision"), action, payload)
                self._json(200, block)
            except WorkspaceConflict as exc:
                self._json(409, {"error": str(exc)})
            except (WorkspaceError, ValueError, UnicodeError) as exc:
                self._json(400, {"error": str(exc)})

    return Handler
