# Ki Knowledge

Knowledge Base System with Graph, Ingestion, and Django UI.

**Status:** 🔄 Under Development
**Purpose:** Extract knowledge from PDFs, JIRA, Ontologies and build a queryable knowledge graph

## Documentation

Start with the [documentation guide](doc/README.md) or
[full index](doc/INDEX.md). The
[2026-10-28 inventory](doc/tracking/project-inventory-2026-10-28.md) distinguishes
the current structure, architectural bottlenecks and proposed cleanup.
Historical plans are kept separately from operating instructions.
For the canonical source tree, wheel contents and checkout requirements, see
the [packaging contract](doc/guides/packaging.md).

## Functional areas

These areas exist in the source tree; this list does not imply that every
planned workflow is complete or deployed.

- 📚 Multi-source Ingestion (PDF, JIRA, CSV, Web, Ontologies)
- 🔗 Knowledge records, relations and graph exploration
- 🔍 Hybrid Search (Semantic + Full-text)
- 💬 Knowledge-based Chat
- 🌐 Django Web UI
- Textwerkstatt: Markdown-Snapshots, eigene Texte mit Revisionen, persistente
  Markierungen und Relationen sowie KI-Gespräch mit explizitem Kontext.
  [Bedienung und Einführung](doc/guides/text-workbench.md).
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
│   ├── services/            # Discovery, import and generation
│   ├── api/                 # FastAPI adapters
│   ├── cli/                 # kictl commands
│   └── wagtail_cms/         # Editorial presentation adapter
├── config/                  # Defaults, stages and stack definition
├── examples/                # Examples and compatibility launchers
├── doc/                     # Categorized documentation; start at doc/README.md
└── tests/                   # Regression and integration tests
```

## widgetkit-django

The reusable dashboard/layout builder is supplied by the sibling packages
`widgetkit` and `widgetkit-django`, not by an in-repository
`ki_knowledge/widgetkit_django/` package. This application provides concrete
registries, views and persistence adapters.
The [live settings editor](doc/guides/live-settings.md) also uses the shared
widgetkit-django UI and ki-core runtime service rather than an app-specific
configuration store.

Documentation:

- [host integration guide](doc/integration/widgetkit-django-host-integration.md)
- [historical extraction log](doc/archive/widgetkit-django-extraction.md)
- [historical packaging roadmap](doc/archive/widgetkit-django-packaging-roadmap.md)

## Frontend assets

See [frontend asset rules](doc/guides/frontend-assets.md) for static CSS/JavaScript
organization, safe template-to-script data handoffs, the inline-block cleanup
inventory, and database-free validation commands.

## Dependencies

The authoritative dependency list is in [pyproject.toml](pyproject.toml).
It includes Django, FastAPI/Uvicorn, Wagtail, PDF/document parsers,
Elasticsearch and PostgreSQL support, and sibling packages such as `ki-core`,
`widgetkit`, `widgetkit-django` and `yaml-cfg-wizard`. Storage targets and
external services depend on the resolved project configuration.

## Installation

Ubuntu 24 (dev or prod host), any directory:

```bash
# Prerequisite: central stackctl user tool (~/.local/bin on PATH).
# Install once from the stackctl checkout: ./scripts/install-user.sh
sudo apt install python3-venv git
git clone https://github.com/uvlightdrops/ki-knowledge.git
cd ki-knowledge
stackctl install            # creates project .venv, installs siblings + this project editable
echo dev-lokal > config/stages/.active_stage   # stage of this host: dev-lokal | prod
stackctl start              # postgres, ollama, API, Django
stackctl run django         # foreground, same stack config; Ctrl+C stops Django
stackctl run api            # foreground API instead
```

The central [stackctl](https://github.com/uvlightdrops/stackctl) user tool is the
canonical lifecycle entry point, invoked from the project directory (or a subdirectory).
It uses the project's interpreter for configuration and service commands, not its own
tool environment. The stack (services, ports, k8s settings) is described
in `config/defaults/stack.yaml` and goes through the normal ki-core configuration, so
stages and `KI_CFG_*` env overrides apply to it as well. `stackctl install` uses
the siblings declared in `pyproject.toml` from the directory next to
this repo (`STACKCTL_SRC_DIR` to change) and clones them there if they are missing.
Existing checkouts are used as they are, so a `git pull` in a sibling is picked up
immediately. Re-run `install` after dependency changes in `pyproject.toml`.

`./kistack` remains a compatibility alias: it delegates to `~/.local/bin/stackctl`
(otherwise `stackctl` on PATH) with this project as cwd. It never installs tools
or creates a project environment itself. The old `examples/run_knowledge_*.py`
launchers forward through that alias to `stackctl -t local run api|django`;
they contain no separate server implementation. No active project venv is needed
to invoke the central tool. Install/update stackctl independently of this project.

Kubernetes: `stackctl -t minikube start` (local cluster, profile `ki-knowledge`) or
`stackctl -t k8s start` (registry + context in `stack.k8s`).
Details: [doc/guides/DJANGO_DEV.md](doc/guides/DJANGO_DEV.md).

YAML configuration and editor operation:
[shared sysadmin guide](doc/guides/YAML_CONFIG_SYSADMIN.md).
Generic design and future ideas live in
[yaml-cfg-wizard](../yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md);
the guide distinguishes current working-tree code from verified deployment.

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
and limits in [doc/integration/NEXTCLOUD.md](doc/integration/NEXTCLOUD.md).

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
