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

## Dependencies

- `ki-core` as local base library (`/home/flow/dev_flow/ki-core`)
- Django
- Elasticsearch / Neo4j
- PDF processing (pypdf, etc.)
- JIRA SDK
- Embeddings (sentence-transformers)

## Installation

```bash
git clone https://github.com/uvlightdrops/ki-knowledge.git
cd ki-knowledge
python3.10 -m venv venv
source venv/bin/activate
pip install -e .
```

The project now uses the local `ki-core` package directly:

```bash
pip install -e /home/flow/dev_flow/ki-core
pip install -e .
```

## License

MIT
