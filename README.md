# Ki Knowledge

Knowledge Base System with Graph, Ingestion, and Django UI.

**Status:** 🔄 Under Development
**Purpose:** Extract knowledge from PDFs, JIRA, Ontologies and build a queryable knowledge graph

## Features (Planned)

- 📚 Multi-source Ingestion (PDF, JIRA, CSV, Web, Ontologies)
- 🔗 Knowledge Graph (Neo4j or similar)
- 🔍 Hybrid Search (Semantic + Full-text)
- 💬 Knowledge-based Chat
- 🌐 Django Web UI
- 📊 Graph Visualization & Exploration

## Structure

```
ki-knowledge/
├── ki_knowledge/
│   ├── knowledge/           # Core knowledge system
│   │   ├── models.py
│   │   ├── ingest.py
│   │   ├── generate.py
│   │   └── ...
│   ├── integrations/        # JIRA, PDF, etc.
│   ├── django_site/         # Web UI
│   └── utils/
├── examples/
│   ├── pdf_import.py
│   ├── jira_integration.py
│   └── ...
└── tests/
```

## widgetkit-django

The reusable dashboard/layout builder extraction now lives in:

- `ki_knowledge/widgetkit_django/`

Documentation:

- extraction log: `doc/widgetkit-django-extraction.md`
- host integration guide: `doc/widgetkit-django-host-integration.md`
- packaging roadmap: `doc/widgetkit-django-packaging-roadmap.md`
- package README: `ki_knowledge/widgetkit_django/README.md`

## Frontend assets

See [frontend asset rules](doc/frontend-assets.md) for static CSS/JavaScript
organization, safe template-to-script data handoffs, the inline-block cleanup
inventory, and database-free validation commands.

## Dependencies

- `ki-core`, `widgetkit-django`, `yaml-cfg-wizard` as sibling repos (not on PyPI)
- Django
- Elasticsearch / Neo4j
- PDF processing (pypdf, etc.)
- JIRA SDK
- Embeddings (sentence-transformers)

## Installation

Ubuntu 24 (dev or prod host), any directory:

```bash
sudo apt install python3-venv git
git clone https://github.com/uvlightdrops/ki-knowledge.git
cd ki-knowledge
./kistack install            # creates .venv, installs stackctl, siblings + this project editable
echo dev-lokal > config/stages/.active_stage   # stage of this host: dev-lokal | prod
./kistack start              # postgres, ollama, API, Django
```

`kistack` is a thin wrapper around [stackctl](https://github.com/uvlightdrops/stackctl), a
project-agnostic start/deploy tool. The stack (services, ports, k8s settings) is described
in `config/defaults/stack.yaml` and goes through the normal ki-core configuration, so
stages and `KI_CFG_*` env overrides apply to it as well. `./kistack install` uses
`stackctl`, `ki-core`, `widgetkit-django` and `yaml_cfg_wizard` from the directory next to
this repo (`STACKCTL_SRC_DIR` to change) and clones them there if they are missing.
Existing checkouts are used as they are, so a `git pull` in a sibling is picked up
immediately. Re-run `install` after dependency changes in `pyproject.toml`.

Kubernetes: `./kistack -t minikube start` (local cluster, profile `ki-knowledge`) or
`./kistack -t k8s start` (registry + context in `stack.k8s`).
Details: [doc/DJANGO_DEV.md](doc/DJANGO_DEV.md).

## Local observation pilot

The opt-in worker samples running ia3simworld without modifying it:

```bash
.venv/bin/python -m ki_knowledge.observation run
.venv/bin/python -m ki_knowledge.observation status
.venv/bin/python -m ki_knowledge.observation once --interval 10 --timeout 5
.venv/bin/python -m ki_knowledge.observation import
.venv/bin/python -m pytest -q tests/test_observation.py
```

Defaults are in `config/defaults/observation.yaml` under `knowledge.observation`;
normal ki-core stage/runtime/`KI_CFG_*` overrides and CLI flags apply. Nothing
starts automatically. `run` stays in the foreground (launch as an attached async
job when needed). Stop the specific worker process to pause; restart with the
same configuration/journal to resume. `--state-db` selects a separate journal;
the default is DataLayout's `observation.sqlite` global state file. Use only one
worker/importer per journal (an OS lock enforces this). `status` is read-only.

These are **1000-tick observation windows, not full simulation sessions**.
Each window retains start/end and sampled intermediate compact responses in
SQLite. Completion requires an observed span **>=1000**; an overshoot is reported
as the actual span, never trimmed to an invented exact boundary. The actual end
sample is reused as the next window's start. Tick/time gaps, unsampled interior
ticks, capture failures, and timestamps are reported. HTTP failures are logged
and retried after the interval with a bounded socket timeout (not a hard
whole-response deadline). Node ID / `createdAt` / source URL changes or tick
regressions mark a partial window **interrupted**, not completed or imported.
Resets entirely between samples that preserve identity and recover the tick
count cannot be detected.

**Fidelity:** snapshots are sampled, and only the most recent 50 string events
are available per snapshot. Complete state/event history is not guaranteed;
events are not deduplicated or represented as a complete ordered history.
Full received compact responses remain in the journal and completed windows
also become `KnowledgeSource`, summary `KnowledgeBlockRecord`, and raw JSON
`KnowledgeArtifact` entries with provenance and SHA-256 in the **configured
local KnowledgeStore** (the same target selection as Django). This is offline
local import, **not remote transport** or the distributed node protocol; no
flowpad calls, embeddings, or LLM calls are made.

Completion is durable before import. Failed imports remain pending; `import`
retries them without contacting the source. Stable persisted observation IDs
and upserts prevent duplicate records even after a crash between stores.
Multi-store writes converge on retry rather than being a cross-store atomic
transaction. Keep the same local target when resuming a journal. Active and
interrupted windows remain inspectable via `status` and the journal; only
completed windows enter the KnowledgeStore. Retention is manual for this small
pilot: snapshots accumulate, so monitor journal size.

## Nextcloud storage (WebDAV)

Opt-in (`apps.ki_knowledge.nextcloud`, disabled by default): list, download and
import Markdown from a per-domain Nextcloud input folder and upload generated
output files create-only (never overwrites). App password only in `creds.yaml`.
`kictl nextcloud status|list|download|import|upload` — details, supported formats
and limits in [doc/NEXTCLOUD.md](doc/NEXTCLOUD.md).

## Chrome DevTools workspace

When running Django locally with `DEBUG=True`, the endpoint
`/.well-known/appspecific/com.chrome.devtools.json` advertises the repository
root and a stable workspace UUID. Open the site via `http://localhost:8000`
or `http://127.0.0.1:8000`, then open Chrome DevTools and approve the workspace
connection when prompted (supported Chrome versions).

The endpoint returns 404 outside debug mode or for non-loopback clients.
No forwarded headers are trusted; a local reverse proxy must restrict access
itself. Chrome and Django must run on the same machine for the advertised
filesystem path to be usable. Connecting the workspace does not automatically
map generated Django HTML back to templates. Review file changes in Git after
editing through DevTools.

## License

MIT
