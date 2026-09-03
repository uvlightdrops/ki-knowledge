# Ki-Knowledge System Overview

**Letzte Aktualisierung:** 2026-09-02  
**Status:** Architecture Review & Refactoring

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Feature Taxonomy](#feature-taxonomy)
3. [Data Flow](#data-flow)
4. [Django Structure](#django-structure)
5. [CLI Structure](#cli-structure)
6. [Integration Points](#integration-points)
7. [Infosite Roadmap](#infosite-roadmap)

---

## System Architecture

### High-Level View

```
┌─────────────────────────────────────────────────────────────────┐
│                    KI-KNOWLEDGE SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │   CLI Layer      │      │   Django Web UI  │                │
│  │  (kictl)         │      │  (localhost:8000)│                │
│  └────────┬─────────┘      └────────┬─────────┘                │
│           │                         │                          │
│           └─────────┬───────────────┘                          │
│                     │                                          │
│  ┌──────────────────┴──────────────────┐                      │
│  │    SERVICE LAYER                    │                      │
│  ├─────────────────────────────────────┤                      │
│  │ • Document Discovery Service        │                      │
│  │ • Import/Processing Pipeline        │                      │
│  │ • Knowledge Block Parser            │                      │
│  │ • InfoSite Generator                │                      │
│  │ • AI Refinement Service             │                      │
│  └────────────────┬─────────────────────┘                      │
│                   │                                            │
│  ┌────────────────┴─────────────────────┐                     │
│  │    DATA & STORAGE LAYER              │                     │
│  ├──────────────────────────────────────┤                     │
│  │ Filesystem:                          │                     │
│  │ • md/<domain>/<working_title>/       │                     │
│  │ • data_out/<domain>/<working_title>/ │                     │
│  │ • pdf/<domain>/                      │                     │
│  │                                      │                     │
│  │ Databases:                           │                     │
│  │ • Django DB (SQLite)                 │                     │
│  │ • Knowledge Cache (~/.ki_cache.db)   │                     │
│  │ • Graph DB (semantic relations)      │                     │
│  └──────────────────────────────────────┘                     │
│                                                                 │
│  ┌──────────────────────────────────────┐                     │
│  │    EXTERNAL INTEGRATIONS             │                     │
│  ├──────────────────────────────────────┤                     │
│  │ • Jira (issue tracking)              │                     │
│  │ • Ollama (local LLM)                 │                     │
│  │ • ki-core (config, AI client)        │                     │
│  │ • Knowledge Blocks (semantic)        │                     │
│  └──────────────────────────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature Taxonomy

### 1. **Data Sources Management**

**Purpose:** Import, organize, and track raw source documents

**Input:** Markdown, PDF, OWL, Jira  
**Output:** Tracked metadata in Django DB + indexed in knowledge cache

**Features:**
- File discovery from configured directories
- Batch PDF import with job tracking
- Jira issue sync with caching
- Full-text indexing for search
- Metadata extraction

**Key Files:**
- `ki_knowledge/integrations/` - Import pipelines
- `ki_knowledge/api/` - FastAPI endpoints
- `ki_knowledge/django_site/views.py` - Dashboard views
- URL: `/data-sources/`, `/pdf-import/`, `/jira/`

**Status:** ✅ Implemented

---

### 2. **Knowledge Blocks** (Semantic Layer)

**Purpose:** Extract hierarchical semantic units from source documents

**Input:** Markdown, quiz YAML, ontologies  
**Output:** Knowledge blocks with embeddings and graph relations

**Features:**
- Markdown → block decomposition (H1, H2, paragraphs, lists, code)
- Local embeddings (using sentence-transformers)
- Graph relations between blocks
- Multiple artifact types (quiz, flashcard, summary)
- FastAPI interface for querying

**Key Files:**
- `ki_knowledge/integrations/markdown_blocks.py`
- `ki_knowledge/integrations/knowledge_store.py`
- `ki_knowledge/integrations/knowledge_graph.py`
- `ki_knowledge/integrations/block_embeddings.py`
- URL: FastAPI at `/api/knowledge/`

**Status:** ✅ Implemented  
**Integration with Infosite:** Phase 4 (future)

---

### 3. **Knowledge Retrieval** (Search & Analysis)

**Purpose:** Find, analyze, and query knowledge across sources

**Features:**
- Hybrid search (keyword + semantic)
- Knowledge graph explorer
- RAG-based semantic chat
- Timeline/temporal analysis

**Key Files:**
- `examples/jira_hybrid_search.py`
- `examples/jira_graph_explorer.py`
- `examples/jira_support_chat.py`
- `examples/jira_daily_timeline.py`

**Status:** ✅ Implemented

---

### 4. **InfoSite** (Knowledge Presentation) ✅ **Implemented, Wagtail migration in progress**

**Purpose:** Generate browsable, markdown-based knowledge presentations

**Input:** Source documents from `md/<domain>/<working_title>/`, abstracted behind a canonical
`DataSource`/`InfoSiteSourceAdapter` layer (`ki_knowledge/knowledge/adapters.py`) so markdown, PDF,
and future source kinds share one discovery/import/path-resolution implementation.
**Output:** Structured markdown in `data_out/<domain>/<working_title>/`

**Phases (completed, in migration order):**

**Phase 1: Foundation** ✅
- [x] Auto-discover source documents
- [x] Track in Django DB (`SourceDocument`, `InfoSiteProject`)
- [x] Display discovered documents in UI (`project_detail` view, `?status=discovered` filter)
- [x] Implement project management views (list/detail/create/edit/delete)
- [x] Link import workflow (Import Control panel)

**Phase 2: Generation** ✅
- [x] Run `InfoSiteGenerator` service
- [x] Track generation status
- [x] Preview generated output (`document_preview.html`)
- [x] Versioning (`infosite_versions` view)

**Phase 3: AI Refinement** ✅
- [x] Integrate ki-core `AIClient`
- [x] Implement refinement modes (Improve/Restructure/Summarize/All)
- [x] Store refined versions

**Phase 4: Advanced / Ongoing Hardening**
- [x] Link to knowledge blocks (semantic extraction → `KnowledgeBlock` publish pipeline, domain "anthro")
- [x] Canonical `DataSource` abstraction unifying md/PDF handling
- [x] Wagtail CMS parallel layer (page models mirror `InfoSiteProject`/`SourceDocument` for gradual cutover)
- [x] Decoupled, job-tracked pipelines: `pipeline_runner.py` (knowledge extraction) and
      `import_runner.py` (document import), both backed by SQLite job-history stores
      (`~/.ki-knowledge/pipeline_jobs.db`), mirroring each other's `enqueue_*`/`run_*_job`/`enqueue_and_run_*` API
- [x] `generate_test_corpus` management command for procedurally generating large synthetic markdown
      corpora (no copyright risk) for volume/UI testing
- [x] Import workflow UX pass: relative (data-root-based) path display, explicit
      "Import-Job starten" action with job history page, hover/arrow-key preview panel reading raw
      source documents (distinct from the generated-output preview), dashboard "🔍 Zu den gefundenen
      Dokumenten" quick link
- [ ] Graph-based navigation
- [ ] Collaborative editing
- [ ] Full Wagtail cutover (currently a parallel/opt-in layer, not yet the primary write path)

**Key Files:**
- `ki_knowledge/django_site/infosite_models.py` - Models
- `ki_knowledge/django_site/infosite_views.py` - Views
- `ki_knowledge/django_site/infosite_urls.py` - Routing
- `ki_knowledge/django_site/infosite_admin.py` - Admin
- `ki_knowledge/infosite/` - Core generator logic
- `ki_knowledge/knowledge/adapters.py` - Canonical `DataSource`/path-resolution adapter
- `ki_knowledge/services/pipeline_runner.py`, `ki_knowledge/services/import_runner.py` - Job-tracked pipelines
- `ki_knowledge/django_site/management/commands/generate_test_corpus.py` - Synthetic test-corpus generator
- URL: `/infosite/`

**Status:** ✅ Implemented and in active use; Wagtail cutover and content-model matrix work ongoing.

---

## Data Flow

### Typical Import & Processing Pipeline

```
1. SOURCE DOCUMENT
   └── md/<domain>/<working_title>/*.md
       or PDF, Jira issue, etc.

2. DISCOVERY SERVICE
   └── Scans filesystem or external source
   └── Extracts metadata (title, path, type)
   └── Creates job entry

3. IMPORT PIPELINE
   ├── PDF → Extract text + metadata
   ├── Markdown → Parse structure
   ├── Jira → Fetch issues + comments
   └── Other → Format-specific handling

4. KNOWLEDGE BLOCK PARSING
   └── Decompose into semantic units
   └── Generate embeddings
   └── Build graph relations

5. DATABASE STORAGE
   ├── Django DB: Project, SourceDocument, ImportJob
   ├── Knowledge Cache: KnowledgeSource, KnowledgeBlock, KnowledgeArtifact
   └── Graph DB: Block relations

6. PRESENTATION LAYER
   ├── Web Dashboard (Django UI)
   ├── Knowledge API (FastAPI)
   ├── Search/Analysis tools
   └── InfoSite generation (Markdown output)
```

---

## Django Structure

### Current URL Hierarchy

```
/
├── admin/                           # Django Admin
│   ├── django_site/infositeproject/
│   └── django_site/sourcedocument/
│
├── data-sources/                    # Data Source Landing
├── knowledge/                       # Knowledge Hub
├── semantic/                        # Semantic Module
├── settings/                        # Settings Landing
│
├── pdf-import/                      # PDF Batch Import
│   ├── jobs/
│   └── report/
│
├── jira/                            # Jira Integration
│   ├── domain-terms/
│   ├── hybrid-search/
│   ├── graph-explorer/
│   └── support-chat/
│
├── infosite/                        # **UNDER REFACTORING**
│   ├── dashboard/                   # Project list
│   └── project/<id>/                # Project detail
│       ├── documents/               # Auto-discovered sources
│       ├── import/                  # Import workflow
│       ├── refine/                  # AI refinement
│       └── preview/                 # Preview output
│
└── ...
```

### Models (infosite_models.py)

```python
InfoSiteProject
├── id (PK)
├── title
├── domain
├── description
├── source_directory          # Path to md/<domain>/<working_title>/
├── enabled
├── last_generated
├── created_at / updated_at
└── relationships
    └── documents (FK: SourceDocument)

SourceDocument
├── id (PK)
├── project (FK)
├── file_path
├── title
├── file_type (md, pdf, txt, etc.)
├── imported (boolean)
├── imported_at
├── created_at / updated_at
└── metadata (JSON)
```

---

## CLI Structure

### kictl Commands

**Dev Tools:**
```
kictl dev
├── django
│   ├── start          # Start dev server
│   ├── stop           # Stop dev server
│   ├── migrate        # Run migrations
│   ├── shell          # Interactive shell
│   └── createsuperuser
├── test               # Run pytest
└── lint               # Run ruff/flake8
```

**Infosite Commands (Future):**
```
kictl infosite
├── init <domain> <title>       # Create new project
├── discover <domain> <title>   # Find source documents
├── import <domain> <title>     # Import to DB
├── generate <domain> <title>   # Generate output
└── refine <domain> <title>     # AI refinement
```

### YAML-Driven Configuration

```yaml
# cli.yaml
commands:
  dev:
    help: "Development Tools"
    commands:
      django:
        help: "Django Development Server"
        commands:
          start:
            callback: "ki_knowledge.cli.commands.dev:django_start"
          # ...
```

---

## Integration Points

### Ki-Core Integration

- **Config System:** `ki_core.config.Config` for application settings
- **AI Client:** `ki_core.ai.AIClient` for LLM-based refinement
- **Data Root:** `config.knowledge_data_root` for base data directory

### External Systems

- **Jira:** OAuth tokens, issue API for syncing
- **Ollama:** Local LLM endpoint for AI refinement
- **Static Site Generators:** Hugo, Jekyll, MkDocs (SSG-compatible markdown)

### Database Layer

- **Django SQLite:** Project metadata, import jobs, user data
- **Knowledge Cache:** `~/.ki_cache.sqlite` for block storage
- **Graph DB:** In-memory or Neo4j-compatible format for relations

---

## Infosite Roadmap

> **Status:** Phases 1–3 below are complete; see [Feature Taxonomy → InfoSite](#4-infosite-knowledge-presentation--implemented-wagtail-migration-in-progress)
> for the up-to-date phase-by-phase checklist. This section is kept as a historical record of the
> original plan plus the follow-on architecture work that has since landed.

### Phase 1: Architecture & Auto-Discovery ✅ Done

Delivered as planned: `DocumentDiscoveryService`/`DocumentSyncService` (`ki_knowledge/services/discovery.py`,
`ki_knowledge/services/sync.py`), `SourceDocument`/`InfoSiteProject` models, project list/detail/edit views,
and the import workflow (discover → select → import).

### Phase 2: Generation & Versioning ✅ Done

`InfoSiteGenerator` is wired into the web UI (`infosite_generate`/`infosite_preview`/`infosite_versions`
views); output lands in `data_out/<domain>/<working_title>/` with version tracking.

### Phase 3: AI Refinement ✅ Done

ki-core `AIClient` integration, refinement modes (Improve/Restructure/Summarize/All), and refined-version
storage are implemented (`infosite_ai_refine`, `infosite_ai_refine_apply`).

### Phase 4: Advanced Features — partially done, ongoing

Completed beyond the original scope:
- **Canonical `DataSource` abstraction** (`ki_knowledge/knowledge/adapters.py`) — markdown and PDF
  sources share one discovery/path-resolution/import implementation instead of format-specific code paths.
- **Knowledge block linking** — semantic extraction pipeline publishes `KnowledgeBlock` records
  (domain `anthro`) from InfoSite source documents; see `knowledge_blocks.md`.
- **Wagtail CMS parallel layer** — Wagtail page models mirror the InfoSite project/document
  structure to enable a gradual, low-risk cutover to Wagtail-native content workflows rather than a
  big-bang rewrite.
- **Decoupled, job-tracked pipelines** — both knowledge extraction (`pipeline_runner.py`) and
  document import (`import_runner.py`) run as tracked jobs with SQLite-backed history and dedicated
  job-list UI pages, instead of synchronous, un-auditable inline operations.
- **Import workflow UX hardening** — relative path display, explicit "Import-Job starten" action,
  hover/arrow-key source preview panel, dashboard quick-links to discovered documents.
- **`generate_test_corpus` tool** — procedurally generates synthetic markdown corpora for
  volume/UI testing without copyright risk.

Still open / not yet done:
- Graph-based navigation across knowledge blocks
- Collaborative editing
- Full Wagtail cutover (currently opt-in/parallel, not the primary write path)
- Broader rollout of the content-model matrix across all domains

---

## Architecture Principles

### 1. **Separation of Concerns**
- **Services:** Business logic (discovery, generation, refinement)
- **Views:** HTTP request/response handling
- **Models:** Data persistence
- **Templates:** HTML presentation

### 2. **Reusability**
- Document discovery logic shared between Data Sources and Infosite
- Import pipeline components reused across formats
- Service layer decoupled from web framework

### 3. **Configuration-Driven**
- Feature flags in settings.py
- Path configuration in ki.yaml
- Database settings environment variables

### 4. **API-First**
- REST endpoints for job management
- FastAPI for knowledge queries
- Django for UI & admin

### 5. **Database Synchronization**
- Filesystem is source of truth
- DB tracks discovered/imported status
- Periodic sync jobs maintain consistency

---

## Current Status

### ✅ Completed
- CLI framework with YAML-driven commands
- Django admin interface & URL routing
- Models for InfoSiteProject and SourceDocument
- Database migrations
- Authentication (Login via Admin)
- Menu integration (Infosite link in nav)
- Document auto-discovery & sync services (`discovery.py`, `sync.py`)
- Project management views (list/detail/edit/delete, discovered-status filter)
- Import workflow with job tracking (`import_runner.py`, import job history UI)
- InfoSiteGenerator service (ki_knowledge.infosite) + generation/preview/versioning views
- AI refinement modes (Improve, Restructure, Summarize, All)
- Knowledge block extraction & publishing pipeline (job-tracked, domain `anthro`)
- Canonical `DataSource`/`InfoSiteSourceAdapter` abstraction (unifies md/PDF handling)
- Wagtail CMS parallel layer (page models mirroring InfoSite structures)
- `generate_test_corpus` management command for synthetic test data
- Import-control UI overhaul: relative path display, hover/arrow-key source preview,
  dashboard "discovered documents" quick link

### 🚧 In Progress
- Gradual Wagtail cutover (parallel layer exists; not yet the primary write path)
- Content-model matrix rollout across domains beyond `anthro`

### ⏳ Pending
- Graph-based navigation across knowledge blocks
- Collaborative editing
- Diff viewer for versioned content

---

## Key References

- **INFOSITE.md** - Technical documentation
- **INFOSITE_ARCHITECTURE.md** - Architecture & refactoring plan
- **knowledge_presentation_requirements.md** - Original requirements
- **IMPORT_AI_REFINEMENT.md** - AI integration guide
- **knowledge_blocks.md** - Semantic layer
- **pdf_batch_import.md** - PDF processing
- **CLI_VS_DJANGO.md** - Interface comparison

---

## Quick Links

| Task | Location | Command |
|------|----------|---------|
| Start Django Dev Server | Terminal | `kictl dev django start` |
| Stop Django Dev Server | Terminal | `kictl dev django stop` |
| Create Superuser | Terminal | `kictl dev django createsuperuser` |
| Open Django Admin | Browser | `http://localhost:8000/admin/` |
| Open Infosite Dashboard | Browser | `http://localhost:8000/infosite/dashboard/` |
| View Database Migrations | Terminal | `python manage.py showmigrations` |
| Run Tests | Terminal | `kictl dev test` |
| Run Linter | Terminal | `kictl dev lint` |

---

**Last Updated:** 2026-09-02  
**Maintainer:** Architecture Review Session
