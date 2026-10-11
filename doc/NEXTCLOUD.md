# Nextcloud storage backend (WebDAV)

First remote storage backend of ki-knowledge: direct WebDAV access to **one**
Nextcloud user. It is plain file transport — it does **not** synchronise
knowledge records or relations (that stays with the node contribution
mechanism, see `doc/distributed-collaboration-plan.md`).

Code: `ki_knowledge/integrations/nextcloud.py` (client),
`ki_knowledge/services/nextcloud_service.py` (domain mapping, cache, import,
upload), CLI `kictl nextcloud ...`. Disabled by default; no UI/API.

## Configuration

Usual ki-core line: defaults → `ki.yaml` → stage → `runtime.yaml` → `KI_CFG_*`
→ `creds.yaml`. Schema defaults are in `schema/ki_knowledge.schema.yaml`.

```yaml
# ki.yaml or stage file
apps:
  ki_knowledge:
    nextcloud:
      enabled: true
      base_url: "https://cloud.example.org"   # https only, sub path allowed (…/nextcloud)
      username: "<login>"
      # user_id: "<id>"          # only if the DAV user id differs from the login
      # dav_path: "remote.php/dav/files/{user_id}"   (default)
      domains:
        anthro:
          input_root: "KI/anthro/input"     # below /remote.php/dav/files/<user_id>/
          output_root: "KI/anthro/output"
      # timeout_seconds: 30, max_download_bytes: 52428800, max_download_seconds: 300,
      # max_listing_bytes: 5242880, max_upload_bytes: 52428800, ca_bundle: ""
```

```yaml
# creds.yaml (not in git) — placeholder only
apps:
  ki_knowledge:
    nextcloud:
      app_password: "<nextcloud-app-password>"
```

Use a Nextcloud **app password** (Settings → Security), not the login password.
`kictl nextcloud status` shows the resolved settings with the password masked
and tells what is missing; it makes no network request.

Rules enforced when a command runs:

- `enabled: false` or missing `base_url`/`username`/`app_password` → `NextcloudConfigError`.
- Only domains listed under `domains` can be used; each needs `input_root` and
  `output_root`. All configured roots must be disjoint (no input/output overlap).
- HTTPS with certificate verification is always on (`ca_bundle` may add a CA).
  Plain `http` is accepted only for loopback hosts with
  `allow_insecure_http_loopback: true` (tests).

## Commands

```bash
kictl nextcloud status
kictl nextcloud list     -d anthro [SUBFOLDER]       # PROPFIND Depth 1, JSON descriptors
kictl nextcloud download -d anthro notes/a.md        # into the local input cache
kictl nextcloud import   -d anthro notes/a.md        # Markdown → KnowledgeStore
kictl nextcloud import   -d anthro --all [SUBFOLDER] # all Markdown directly in the folder
kictl nextcloud upload   -d anthro site/index.html [--mkdirs]
```

(`kictl` = `python -m ki_knowledge.cli.main`.) Paths for `list`/`download`/`import`
are relative to the domain's `input_root`; `..`, `.`, empty segments, backslashes
and control characters are rejected, so nothing outside the input root is read.

## Input: download and import

- Downloads land in `DataLayout.remote_input_cache_dir(domain, "nextcloud")`
  (`<domain>/derived/remote/nextcloud/input/{files,meta}` in layout v3) — never in
  local source folders or the output tree, so local imports are not overwritten.
- Streaming download with byte and wall-clock limits (budget starts before the
  request; each socket read is capped too), written to a temp file and
  renamed atomically; on any error the previous cache file stays and no partial
  file remains. A repeated download sends `If-None-Match: <ETag>`; 304 keeps the
  cached file.
- **Supported import: Markdown (`.md`, `.markdown`, UTF-8) only.** Other types fail
  with `NextcloudUnsupportedTypeError` before any download; `--all` lists them as
  skipped (never as imported). Folders are not imported recursively.
- Import reuses `KnowledgeStore.import_markdown_text` (replace mode) with
  `source_type: nextcloud_markdown`. Provenance is the **remote** identity:
  source `location` = remote WebDAV URL, `metadata.provenance` = instance, user id,
  domain, remote path/URL, ETag, Nextcloud file id, size, last modified, SHA-256
  (local cache path only as additional info). Every record carries
  `metadata.remote` (URL, ETag, file id).
- `source_id` = `nextcloud:<host>:<user_id>:fileid:<file id>` — stable across
  content changes (new ETag) and renames; re-import replaces stale blocks.
- Domain knowledge views and node contribution selection attribute Nextcloud
  sources through `metadata.domain`, independently of their remote URL.

## Output: upload

- Only generated files inside `DataLayout.output_dir(domain)` are accepted
  (relative paths are relative to it; symlinks pointing outside are rejected).
  The remote path mirrors the path below the output dir under `output_root`.
- `PUT` always sends `If-None-Match: *`: an existing remote file yields HTTP 412
  → `NextcloudConflictError`; nothing is overwritten, versioned or deleted. A
  2xx other than `201 Created` is reported as an error.
- Missing parent folders → 409 error unless `--mkdirs` (MKCOL only below
  `output_root`; the output root itself must exist).

## Security behaviour

- Redirects are never followed (3xx → `NextcloudRedirectError`), so credentials
  are not sent elsewhere.
- Every `href` of a PROPFIND answer must stay on the same host, inside the
  user's files root and be the requested collection or a direct child.
- PROPFIND requires HTTP 207 with an XML content type, size-bounded body, parsed
  with expat; DTDs/entity declarations are rejected.
- Errors: `NextcloudAuthError` (401/403), `NextcloudNotFoundError`,
  `NextcloudConflictError`, `NextcloudRedirectError`, `NextcloudResponseError`
  (status/non-XML/malformed XML), `NextcloudSizeError`, `NextcloudTransportError`
  (TLS, timeout, connection), `NextcloudPathError`. The password never appears in
  reprs, URLs, errors or logs.

## Limits

No recursive sync, no deletion, no overwrite/versioning on upload, no chunked
upload (single PUT up to `max_upload_bytes`), no OCS/share API, Markdown only for
import. Tests (`tests/test_nextcloud.py`) use a loopback WebDAV fixture; no real
Nextcloud was contacted.
