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

- extraction log: `docs/widgetkit-django-extraction.md`
- host integration guide: `docs/widgetkit-django-host-integration.md`
- packaging roadmap: `docs/widgetkit-django-packaging-roadmap.md`
- package README: `ki_knowledge/widgetkit_django/README.md`

## Frontend assets

See [frontend asset rules](docs/frontend-assets.md) for static CSS/JavaScript
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
./kistack install            # creates .venv, installs siblings + this project editable
cp deploy/stack.env.example deploy/stack.env   # optional: hosts/ports per host
./kistack start              # postgres, ollama check, API, Django
```

`./kistack install` uses `ki-core`, `widgetkit-django` and `yaml_cfg_wizard` from the
directory next to this repo (`KI_SRC_DIR` to change) and clones them there if they are
missing. Existing checkouts are used as they are, so a `git pull` in a sibling is picked
up immediately. Re-run `install` after dependency changes in `pyproject.toml`.
Details: [doc/DJANGO_DEV.md](doc/DJANGO_DEV.md).

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
