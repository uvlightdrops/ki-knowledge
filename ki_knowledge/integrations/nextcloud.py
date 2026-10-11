"""Direct Nextcloud WebDAV client (read/list/download, create-only upload).

Scope (deliberately small):

* ``PROPFIND`` with ``Depth: 0`` / ``Depth: 1`` (no recursive listing),
* streaming ``GET`` with size and wall-clock bounds, conditional on the ETag,
  written atomically to a local file,
* ``PUT`` with ``If-None-Match: *`` only, so an existing remote file is never
  overwritten (HTTP 412 -> :class:`NextcloudConflictError`),
* ``MKCOL`` for explicitly requested parent collections.

Security rules: HTTPS with certificate verification always (plain HTTP only for
loopback hosts and only when ``allow_insecure_http_loopback`` is set), redirects
are never followed (auth must not travel to another location), every remote
path and every server ``href`` is validated against the configured files root,
and PROPFIND XML is parsed with expat while DTDs/entities are rejected and the
body size is bounded. Credentials never appear in reprs, URLs, errors or logs.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import quote, unquote, urlsplit
from xml.parsers import expat

import requests

LOG = logging.getLogger(__name__)

CONFIG_PATH = "apps.ki_knowledge.nextcloud"
DEFAULT_DAV_PATH = "remote.php/dav/files/{user_id}"
MiB = 1024 * 1024

_DAV = "DAV:"
_OC = "http://owncloud.org/ns"
_NC = "http://nextcloud.org/ns"
_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
    "<d:prop><d:resourcetype/><d:getetag/><d:getlastmodified/><d:getcontentlength/>"
    "<d:getcontenttype/><oc:fileid/><oc:size/></d:prop></d:propfind>"
).encode("utf-8")
_MAX_XML_DEPTH = 32
_SEGMENT_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f\\/]")
_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


# --- errors ------------------------------------------------------------------------


class NextcloudError(RuntimeError):
    """Base class of all Nextcloud backend errors."""


class NextcloudConfigError(NextcloudError):
    """Backend disabled or configuration incomplete/invalid."""


class NextcloudPathError(NextcloudError):
    """Path traversal, root escape or a server href outside the expected location."""


class NextcloudTransportError(NextcloudError):
    """Connection/TLS failure or timeout."""


class NextcloudRedirectError(NextcloudError):
    """Server answered with a redirect; redirects are never followed."""


class NextcloudResponseError(NextcloudError):
    """Unexpected status, non-XML or malformed/unsafe XML response."""


class NextcloudSizeError(NextcloudError):
    """Response or upload exceeds the configured bound."""


class NextcloudHTTPError(NextcloudError):
    """Unexpected HTTP status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class NextcloudAuthError(NextcloudHTTPError):
    """HTTP 401/403: wrong app password or missing permission."""


class NextcloudNotFoundError(NextcloudHTTPError):
    """HTTP 404."""


class NextcloudConflictError(NextcloudHTTPError):
    """Remote file already exists (412 on create-only upload) or parent missing (409)."""


class NextcloudUnsupportedTypeError(NextcloudError):
    """File type cannot be imported."""


# --- settings ----------------------------------------------------------------------


def validate_segment(segment: str) -> str:
    if not segment or segment in {".", ".."} or _SEGMENT_FORBIDDEN.search(segment):
        raise NextcloudPathError(f"invalid remote path segment: {segment!r}")
    return segment


def split_remote_path(path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    """Split a remote path (relative to the files root) into validated segments.

    Leading/trailing slashes are ignored, empty inner segments, ``.``/``..``,
    backslashes and control characters are rejected.
    """
    if not isinstance(path, str):
        raise NextcloudPathError("remote path must be a string")
    stripped = path.strip("/")
    if not stripped:
        if allow_empty:
            return ()
        raise NextcloudPathError("remote path must not be empty")
    return tuple(validate_segment(part) for part in stripped.split("/"))


def join_remote(*parts: Iterable[str]) -> str:
    return "/".join(segment for part in parts for segment in part)


def is_within(path: tuple[str, ...], root: tuple[str, ...]) -> bool:
    return path[: len(root)] == root


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class DomainRoots:
    """Remote input/output roots of one domain (segments below the user's files root)."""

    domain: str
    input_root: tuple[str, ...]
    output_root: tuple[str, ...]


@dataclass(frozen=True)
class NextcloudSettings:
    """Resolved ``apps.ki_knowledge.nextcloud`` settings."""

    enabled: bool = False
    base_url: str = ""
    username: str = ""
    app_password: str = field(default="", repr=False)
    user_id: str = ""
    dav_path: str = DEFAULT_DAV_PATH
    timeout_seconds: float = 30.0
    max_download_bytes: int = 50 * MiB
    max_download_seconds: float = 300.0
    max_listing_bytes: int = 5 * MiB
    max_upload_bytes: int = 50 * MiB
    allow_insecure_http_loopback: bool = False
    ca_bundle: str = ""
    domains: dict[str, DomainRoots] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "NextcloudSettings":
        data = dict(data or {})
        domains: dict[str, DomainRoots] = {}
        raw_domains = data.get("domains") or {}
        if not isinstance(raw_domains, dict):
            raise NextcloudConfigError(f"{CONFIG_PATH}.domains must be a mapping <domain>: {{input_root, output_root}}")
        for name, roots in raw_domains.items():
            name = str(name)
            if not _DOMAIN_PATTERN.match(name) or name in {".", ".."}:
                raise NextcloudConfigError(f"{CONFIG_PATH}.domains: invalid domain name {name!r}")
            roots = roots or {}
            if not isinstance(roots, dict):
                raise NextcloudConfigError(f"{CONFIG_PATH}.domains.{name} must be a mapping")
            try:
                input_root = split_remote_path(str(roots.get("input_root") or ""))
                output_root = split_remote_path(str(roots.get("output_root") or ""))
            except NextcloudPathError as exc:
                raise NextcloudConfigError(f"{CONFIG_PATH}.domains.{name}: {exc}") from None
            domains[name] = DomainRoots(name, input_root, output_root)

        def number(key: str, default: float, kind: Callable[[Any], float] = float) -> Any:
            value = data.get(key)
            if value in (None, ""):
                return default
            try:
                result = kind(value)
            except (TypeError, ValueError):
                raise NextcloudConfigError(f"{CONFIG_PATH}.{key} must be a number") from None
            if result <= 0:
                raise NextcloudConfigError(f"{CONFIG_PATH}.{key} must be positive")
            return result

        return cls(
            enabled=bool(data.get("enabled", False)),
            base_url=str(data.get("base_url") or "").strip(),
            username=str(data.get("username") or "").strip(),
            app_password=str(data.get("app_password") or ""),
            user_id=str(data.get("user_id") or "").strip(),
            dav_path=str(data.get("dav_path") or DEFAULT_DAV_PATH).strip(),
            timeout_seconds=number("timeout_seconds", 30.0),
            max_download_bytes=number("max_download_bytes", 50 * MiB, int),
            max_download_seconds=number("max_download_seconds", 300.0),
            max_listing_bytes=number("max_listing_bytes", 5 * MiB, int),
            max_upload_bytes=number("max_upload_bytes", 50 * MiB, int),
            allow_insecure_http_loopback=bool(data.get("allow_insecure_http_loopback", False)),
            ca_bundle=str(data.get("ca_bundle") or "").strip(),
            domains=domains,
        )

    @classmethod
    def from_config(cls, cfg: Any = None) -> "NextcloudSettings":
        """Read the settings from the ki-core config (defaults -> stage -> runtime -> creds)."""
        if cfg is None:
            from ki_knowledge.app_config import AppConfig

            cfg = AppConfig.from_env()
        raw = getattr(cfg, "raw", cfg)
        section = raw.get_path(CONFIG_PATH, {}) if hasattr(raw, "get_path") else (
            ((raw or {}).get("apps", {}) or {}).get("ki_knowledge", {}) or {}
        ).get("nextcloud", {})
        return cls.from_mapping(section if isinstance(section, dict) else {})

    def require_ready(self) -> None:
        """Raise :class:`NextcloudConfigError` unless the backend can be used."""
        if not self.enabled:
            raise NextcloudConfigError(f"Nextcloud backend is disabled ({CONFIG_PATH}.enabled is false)")
        missing = [key for key in ("base_url", "username", "app_password") if not getattr(self, key)]
        if missing:
            hint = " (app_password belongs in creds.yaml)" if "app_password" in missing else ""
            raise NextcloudConfigError(
                "Nextcloud config incomplete, missing: " + ", ".join(f"{CONFIG_PATH}.{key}" for key in missing) + hint
            )
        url = urlsplit(self.base_url)
        if url.scheme not in {"https", "http"} or not url.hostname:
            raise NextcloudConfigError(f"{CONFIG_PATH}.base_url must be an absolute https URL")
        if url.username or url.password or url.query or url.fragment:
            raise NextcloudConfigError(f"{CONFIG_PATH}.base_url must not contain credentials, query or fragment")
        if url.scheme == "http":
            if not _is_loopback(url.hostname):
                raise NextcloudConfigError(f"{CONFIG_PATH}.base_url must use https (http only for loopback tests)")
            if not self.allow_insecure_http_loopback:
                raise NextcloudConfigError(
                    f"plain http requires {CONFIG_PATH}.allow_insecure_http_loopback: true (loopback tests only)"
                )
        if "{user_id}" not in self.dav_path and "{username}" not in self.dav_path:
            raise NextcloudConfigError(f"{CONFIG_PATH}.dav_path must contain {{user_id}}")
        try:
            split_remote_path(self.dav_path.replace("{user_id}", "u").replace("{username}", "u"), allow_empty=False)
        except NextcloudPathError as exc:
            raise NextcloudConfigError(f"{CONFIG_PATH}.dav_path: {exc}") from None
        if self.ca_bundle and not Path(self.ca_bundle).expanduser().is_file():
            raise NextcloudConfigError(f"{CONFIG_PATH}.ca_bundle does not exist: {self.ca_bundle}")
        self._check_root_separation()

    def _check_root_separation(self) -> None:
        roots: list[tuple[str, tuple[str, ...]]] = []
        for domain in self.domains.values():
            for kind, root in (("input_root", domain.input_root), ("output_root", domain.output_root)):
                if root:
                    roots.append((f"{domain.domain}.{kind}", root))
        for index, (name, root) in enumerate(roots):
            for other_name, other in roots[index + 1:]:
                if is_within(root, other) or is_within(other, root):
                    raise NextcloudConfigError(
                        f"{CONFIG_PATH}.domains: {name} and {other_name} overlap; input and output roots must be disjoint"
                    )

    def roots_for(self, domain: str) -> DomainRoots:
        self.require_ready()
        roots = self.domains.get(domain)
        if roots is None:
            known = ", ".join(sorted(self.domains)) or "-"
            raise NextcloudConfigError(f"domain {domain!r} has no Nextcloud mapping in {CONFIG_PATH}.domains (configured: {known})")
        if not roots.input_root or not roots.output_root:
            raise NextcloudConfigError(f"{CONFIG_PATH}.domains.{domain} needs non-empty input_root and output_root")
        return roots

    @property
    def effective_user_id(self) -> str:
        return self.user_id or self.username

    def safe_summary(self) -> dict[str, Any]:
        """Settings without secrets (for status output)."""
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "username": self.username,
            "app_password": "***" if self.app_password else "",
            "dav_path": self.dav_path,
            "domains": {
                name: {"input_root": "/".join(r.input_root), "output_root": "/".join(r.output_root)}
                for name, r in sorted(self.domains.items())
            },
        }


# --- results -----------------------------------------------------------------------


@dataclass(frozen=True)
class RemoteEntry:
    """One PROPFIND result; ``path`` is relative to the user's files root."""

    path: str
    url: str
    is_dir: bool
    etag: Optional[str] = None
    file_id: Optional[str] = None
    size: Optional[int] = None
    last_modified: Optional[str] = None
    content_type: Optional[str] = None

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class DownloadResult:
    entry: RemoteEntry
    local_path: Path
    etag: Optional[str]
    sha256: Optional[str]
    size: Optional[int]
    not_modified: bool


@dataclass(frozen=True)
class UploadResult:
    path: str
    url: str
    etag: Optional[str]
    file_id: Optional[str]
    size: int
    sha256: str


# --- XML ---------------------------------------------------------------------------


class _Node:
    __slots__ = ("tag", "children", "text")

    def __init__(self, tag: str):
        self.tag = tag
        self.children: list[_Node] = []
        self.text: list[str] = []

    def find(self, tag: str) -> Optional["_Node"]:
        return next((child for child in self.children if child.tag == tag), None)

    def findall(self, tag: str) -> list["_Node"]:
        return [child for child in self.children if child.tag == tag]

    def value(self) -> str:
        return "".join(self.text).strip()


def _tag(namespace: str, name: str) -> str:
    return f"{namespace} {name}"


def parse_xml_safely(body: bytes) -> _Node:
    """Parse XML with expat; DTDs, entity declarations and external entities are rejected."""

    def reject(*_args: Any) -> None:
        raise NextcloudResponseError("unsafe XML: DTD/entity declarations are not allowed")

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.UnparsedEntityDeclHandler = reject
    parser.NotationDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    root = _Node("#document")
    stack = [root]

    def start(tag: str, _attrs: dict) -> None:
        if len(stack) > _MAX_XML_DEPTH:
            raise NextcloudResponseError("XML nesting too deep")
        node = _Node(tag)
        stack[-1].children.append(node)
        stack.append(node)

    def end(_tag: str) -> None:
        stack.pop()

    def text(data: str) -> None:
        stack[-1].text.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    try:
        parser.Parse(body, True)
    except expat.ExpatError as exc:
        raise NextcloudResponseError(f"malformed XML response: {exc}") from None
    if len(root.children) != 1:
        raise NextcloudResponseError("malformed XML response: no root element")
    return root.children[0]


# --- client ------------------------------------------------------------------------


def _etag(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


class NextcloudWebDAVClient:
    """Minimal WebDAV client bound to one user's files root."""

    def __init__(self, settings: NextcloudSettings, session: Optional[requests.Session] = None):
        settings.require_ready()
        self.settings = settings
        base = urlsplit(settings.base_url)
        self._scheme = base.scheme
        self._netloc = base.netloc.lower()
        base_segments = split_remote_path(unquote(base.path))
        dav = settings.dav_path.replace("{user_id}", settings.effective_user_id).replace(
            "{username}", settings.effective_user_id
        )
        self._root_segments = base_segments + split_remote_path(dav, allow_empty=False)
        self._root_url = f"{base.scheme}://{base.netloc}/" + "/".join(quote(s, safe="") for s in self._root_segments)
        self._session = session or requests.Session()
        self._session.auth = (settings.username, settings.app_password)
        # Plain-http loopback mode is test-only; ignore proxy env vars there.
        self._session.trust_env = base.scheme == "https"
        self._verify: bool | str = str(Path(settings.ca_bundle).expanduser()) if settings.ca_bundle else True

    def __repr__(self) -> str:
        return f"NextcloudWebDAVClient(root={self._root_url!r})"

    @property
    def root_url(self) -> str:
        return self._root_url

    def url_for(self, path: str | tuple[str, ...]) -> str:
        segments = path if isinstance(path, tuple) else split_remote_path(path)
        for segment in segments:
            validate_segment(segment)
        suffix = "/".join(quote(s, safe="") for s in segments)
        return self._root_url + ("/" + suffix if suffix else "")

    # -- transport --

    def _request(
        self, method: str, path: tuple[str, ...], *, timeout: Optional[float] = None, **kwargs: Any
    ) -> requests.Response:
        url = self.url_for(path)
        timeout = timeout or self.settings.timeout_seconds
        try:
            response = self._session.request(
                method, url, allow_redirects=False, verify=self._verify, timeout=(timeout, timeout), **kwargs
            )
        except requests.exceptions.SSLError as exc:
            raise NextcloudTransportError(f"{method} {self._display(path)}: TLS verification failed ({type(exc).__name__})") from None
        except requests.Timeout:
            raise NextcloudTransportError(f"{method} {self._display(path)}: timed out after {timeout}s") from None
        except requests.RequestException as exc:
            raise NextcloudTransportError(f"{method} {self._display(path)}: connection failed ({type(exc).__name__})") from None
        LOG.debug("nextcloud %s %s -> %s", method, self._display(path), response.status_code)
        if 300 <= response.status_code < 400 and response.status_code != 304:
            response.close()
            raise NextcloudRedirectError(
                f"{method} {self._display(path)}: server redirected (HTTP {response.status_code}); redirects are not followed"
            )
        return response

    @staticmethod
    def _display(path: tuple[str, ...]) -> str:
        return "/" + "/".join(path)

    def _raise_for_status(self, method: str, path: tuple[str, ...], response: requests.Response) -> None:
        status = response.status_code
        response.close()
        where = f"{method} {self._display(path)}"
        if status in (401, 403):
            raise NextcloudAuthError(f"{where}: authentication/permission denied (HTTP {status})", status)
        if status == 404:
            raise NextcloudNotFoundError(f"{where}: not found (HTTP 404)", status)
        raise NextcloudHTTPError(f"{where}: unexpected HTTP {status}", status)

    def _read_bounded(self, response: requests.Response, limit: int, what: str) -> bytes:
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > limit:
            response.close()
            raise NextcloudSizeError(f"{what}: response of {declared} bytes exceeds limit {limit}")
        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > limit:
                    raise NextcloudSizeError(f"{what}: response exceeds limit {limit} bytes")
                chunks.append(chunk)
        except requests.RequestException as exc:
            raise NextcloudTransportError(f"{what}: read failed ({type(exc).__name__})") from None
        finally:
            response.close()
        return b"".join(chunks)

    # -- PROPFIND --

    def _href_segments(self, href: str) -> tuple[str, ...]:
        parts = urlsplit(href.strip())
        if parts.scheme or parts.netloc:
            if parts.scheme != self._scheme or parts.netloc.lower() != self._netloc:
                raise NextcloudPathError(f"server href points to another host: {href!r}")
        if parts.query or parts.fragment:
            raise NextcloudPathError(f"server href with query/fragment: {href!r}")
        raw = parts.path
        if not raw.startswith("/"):
            raise NextcloudPathError(f"server href is not absolute: {href!r}")
        raw = raw.strip("/")
        segments = []
        for piece in raw.split("/") if raw else []:
            decoded = unquote(piece)
            try:
                segments.append(validate_segment(decoded))
            except NextcloudPathError:
                raise NextcloudPathError(f"server href with invalid segment: {href!r}") from None
        root = self._root_segments
        if tuple(segments[: len(root)]) != root:
            raise NextcloudPathError(f"server href outside the files root: {href!r}")
        return tuple(segments[len(root):])

    def propfind(self, path: str | tuple[str, ...], depth: int = 1) -> list[RemoteEntry]:
        if depth not in (0, 1):
            raise ValueError("depth must be 0 or 1")
        segments = path if isinstance(path, tuple) else split_remote_path(path)
        response = self._request(
            "PROPFIND",
            segments,
            data=_PROPFIND_BODY,
            headers={"Depth": str(depth), "Content-Type": "application/xml; charset=utf-8"},
            stream=True,
        )
        if response.status_code != 207:
            self._raise_for_status("PROPFIND", segments, response)
        content_type = response.headers.get("Content-Type", "")
        if "xml" not in content_type.lower():
            response.close()
            raise NextcloudResponseError(f"PROPFIND {self._display(segments)}: non-XML response ({content_type or 'no content type'})")
        body = self._read_bounded(response, self.settings.max_listing_bytes, f"PROPFIND {self._display(segments)}")
        root = parse_xml_safely(body)
        if root.tag != _tag(_DAV, "multistatus"):
            raise NextcloudResponseError(f"PROPFIND {self._display(segments)}: expected DAV multistatus")
        entries: list[RemoteEntry] = []
        for item in root.findall(_tag(_DAV, "response")):
            href_node = item.find(_tag(_DAV, "href"))
            if href_node is None or not href_node.value():
                raise NextcloudResponseError("PROPFIND response entry without href")
            relative = self._href_segments(href_node.value())
            if relative != segments and not (len(relative) == len(segments) + 1 and is_within(relative, segments)):
                raise NextcloudPathError(f"server href outside the requested collection: {href_node.value()!r}")
            if depth == 0 and relative != segments:
                raise NextcloudPathError("Depth 0 response contains a child entry")
            entries.append(self._entry(relative, item))
        if not any(entry.path == join_remote(segments) for entry in entries):
            raise NextcloudResponseError(f"PROPFIND {self._display(segments)}: requested resource missing from response")
        return entries

    def _entry(self, segments: tuple[str, ...], item: _Node) -> RemoteEntry:
        props: dict[str, _Node] = {}
        for propstat in item.findall(_tag(_DAV, "propstat")):
            status = propstat.find(_tag(_DAV, "status"))
            if status is None or " 200 " not in f" {status.value()} ":
                continue
            prop = propstat.find(_tag(_DAV, "prop"))
            for child in prop.children if prop is not None else []:
                props[child.tag] = child

        def text(namespace: str, name: str) -> Optional[str]:
            node = props.get(_tag(namespace, name))
            return node.value() or None if node is not None else None

        resourcetype = props.get(_tag(_DAV, "resourcetype"))
        is_dir = resourcetype is not None and resourcetype.find(_tag(_DAV, "collection")) is not None
        size_text = text(_DAV, "getcontentlength") or text(_OC, "size")
        try:
            size = int(size_text) if size_text is not None else None
        except ValueError:
            raise NextcloudResponseError(f"invalid size {size_text!r} in PROPFIND response") from None
        return RemoteEntry(
            path=join_remote(segments),
            url=self.url_for(segments),
            is_dir=is_dir,
            etag=_etag(text(_DAV, "getetag")),
            file_id=text(_OC, "fileid"),
            size=size,
            last_modified=text(_DAV, "getlastmodified"),
            content_type=text(_DAV, "getcontenttype"),
        )

    def stat(self, path: str | tuple[str, ...]) -> RemoteEntry:
        segments = path if isinstance(path, tuple) else split_remote_path(path)
        return self.propfind(segments, depth=0)[0]

    def list(self, path: str | tuple[str, ...]) -> list[RemoteEntry]:
        """Direct children of a collection (``Depth: 1``), without the collection itself."""
        segments = path if isinstance(path, tuple) else split_remote_path(path)
        entries = self.propfind(segments, depth=1)
        own = join_remote(segments)
        parent = next(entry for entry in entries if entry.path == own)
        if not parent.is_dir:
            raise NextcloudResponseError(f"{self._display(segments)} is not a collection")
        return sorted((entry for entry in entries if entry.path != own), key=lambda e: (not e.is_dir, e.path))

    # -- GET --

    def download(
        self,
        path: str | tuple[str, ...],
        target: Path,
        *,
        if_none_match: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[str], int]:
        """Stream a file into ``target`` atomically.

        Returns ``(not_modified, etag, sha256, size)``. With ``if_none_match``
        and an existing ``target`` a 304 answer leaves the file untouched.
        """
        segments = path if isinstance(path, tuple) else split_remote_path(path, allow_empty=False)
        headers = {"Accept-Encoding": "identity"}
        conditional = bool(if_none_match and target.is_file())
        if conditional:
            headers["If-None-Match"] = if_none_match
        # Wall-clock budget covers headers and body; each blocking socket read is
        # capped as well, so the total is bounded by budget + one read timeout.
        budget = self.settings.max_download_seconds
        deadline = time.monotonic() + budget
        response = self._request(
            "GET", segments, headers=headers, stream=True, timeout=min(self.settings.timeout_seconds, budget)
        )
        if response.status_code == 304:
            response.close()
            if not conditional:
                raise NextcloudResponseError(f"GET {self._display(segments)}: unexpected 304")
            return True, if_none_match, None, target.stat().st_size
        if response.status_code != 200:
            self._raise_for_status("GET", segments, response)
        limit = self.settings.max_download_bytes
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > limit:
            response.close()
            raise NextcloudSizeError(f"GET {self._display(segments)}: {declared} bytes exceeds limit {limit}")
        etag = _etag(response.headers.get("ETag"))
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                try:
                    for chunk in response.iter_content(64 * 1024):
                        total += len(chunk)
                        if total > limit:
                            raise NextcloudSizeError(f"GET {self._display(segments)}: exceeds limit {limit} bytes")
                        if time.monotonic() > deadline:
                            raise NextcloudTransportError(
                                f"GET {self._display(segments)}: exceeded {self.settings.max_download_seconds}s download time"
                            )
                        digest.update(chunk)
                        handle.write(chunk)
                except requests.RequestException as exc:
                    raise NextcloudTransportError(f"GET {self._display(segments)}: read failed ({type(exc).__name__})") from None
                handle.flush()
                os.fsync(handle.fileno())
            if declared and declared.isdigit() and int(declared) != total:
                raise NextcloudTransportError(f"GET {self._display(segments)}: truncated ({total} of {declared} bytes)")
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        finally:
            response.close()
        return False, etag, digest.hexdigest(), total

    # -- PUT / MKCOL --

    def mkcol(self, path: tuple[str, ...]) -> bool:
        """Create a collection; returns ``False`` if it already exists."""
        response = self._request("MKCOL", path)
        status = response.status_code
        if status == 201:
            response.close()
            return True
        if status == 405:
            response.close()
            return False
        if status == 409:
            response.close()
            raise NextcloudConflictError(f"MKCOL {self._display(path)}: parent collection missing (HTTP 409)", 409)
        self._raise_for_status("MKCOL", path, response)
        return False  # pragma: no cover

    def upload_new(self, path: tuple[str, ...], source: Path, *, content_type: str = "application/octet-stream") -> UploadResult:
        """PUT ``source`` to ``path`` only if nothing exists there (``If-None-Match: *``)."""
        size = source.stat().st_size
        if size > self.settings.max_upload_bytes:
            raise NextcloudSizeError(f"upload {source.name}: {size} bytes exceeds limit {self.settings.max_upload_bytes}")
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        with source.open("rb") as handle:
            response = self._request(
                "PUT",
                path,
                data=handle,
                headers={"If-None-Match": "*", "Content-Type": content_type, "Content-Length": str(size)},
            )
        status = response.status_code
        if status == 412:
            response.close()
            raise NextcloudConflictError(
                f"PUT {self._display(path)}: remote file already exists (HTTP 412); not overwritten", 412
            )
        if status == 409:
            response.close()
            raise NextcloudConflictError(f"PUT {self._display(path)}: parent collection missing (HTTP 409)", 409)
        if status in (200, 204):
            response.close()
            raise NextcloudResponseError(
                f"PUT {self._display(path)}: server answered HTTP {status} instead of 201 Created despite If-None-Match: *"
            )
        if status != 201:
            self._raise_for_status("PUT", path, response)
        etag = _etag(response.headers.get("ETag") or response.headers.get("OC-ETag"))
        file_id = (response.headers.get("OC-FileId") or "").strip() or None
        response.close()
        return UploadResult(join_remote(path), self.url_for(path), etag, file_id, size, digest.hexdigest())


__all__ = [
    "CONFIG_PATH",
    "DomainRoots",
    "DownloadResult",
    "NextcloudAuthError",
    "NextcloudConfigError",
    "NextcloudConflictError",
    "NextcloudError",
    "NextcloudHTTPError",
    "NextcloudNotFoundError",
    "NextcloudPathError",
    "NextcloudRedirectError",
    "NextcloudResponseError",
    "NextcloudSettings",
    "NextcloudSizeError",
    "NextcloudTransportError",
    "NextcloudUnsupportedTypeError",
    "NextcloudWebDAVClient",
    "RemoteEntry",
    "UploadResult",
    "is_within",
    "join_remote",
    "parse_xml_safely",
    "split_remote_path",
]
