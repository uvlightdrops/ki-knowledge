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

### 4. **InfoSite** (Knowledge Presentation) 🚀 **CURRENTLY REFACTORING**

**Purpose:** Generate browsable, markdown-based knowledge presentations

**Input:** Source documents from `md/<domain>/<working_title>/`  
**Output:** Structured markdown in `data_out/<domain>/<working_title>/`

**Phases:**

**Phase 1: Foundation (NOW - Ready to implement)**
- [x] Auto-discover source documents
- [x] Track in Django DB (models created)
- [ ] Display discovered documents in UI
- [ ] Implement project management views
- [ ] Link import workflow

**Phase 2: Generation (Next)**
- [ ] Run InfoSiteGenerator service
- [ ] Track generation status
- [ ] Preview generated output
- [ ] Versioning (v1-original baseline)

**Phase 3: AI Refinement (Later)**
- [ ] Integrate ki-core AIClient
- [ ] Implement refinement modes
- [ ] Store refined versions

**Phase 4: Advanced (Future)**
- [ ] Link to knowledge blocks
- [ ] Graph-based navigation
- [ ] Collaborative editing
- [ ] Version history viewing

**Key Files:**
- `ki_knowledge/django_site/infosite_models.py` - Models
- `ki_knowledge/django_site/infosite_views.py` - Views
- `ki_knowledge/django_site/infosite_urls.py` - Routing
- `ki_knowledge/django_site/infosite_admin.py` - Admin
- `ki_knowledge/infosite/` - Core generator logic
- URL: `/infosite/`

**Status:** 🚧 Under refactoring (see INFOSITE_ARCHITECTURE.md)

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

### Phase 1: Architecture & Auto-Discovery ✅ Ready to implement

**Goals:**
- Unify document discovery logic (reusable for Data Sources + Infosite)
- Auto-find source documents in `md/<domain>/<working_title>/`
- Display discovered documents in UI with sync status

**Tasks:**
1. Create `DocumentDiscoveryService` (unified file finder)
   - `find_infosite_documents(domain, working_title)`
   - Returns: list of `FileInfo(path, name, type, size, mtime)`

2. Update `SourceDocument` model
   - Add `source_file_path` field
   - Add `last_sync_at` timestamp
   - Add `auto_discovered` boolean

3. Implement InfoSite project views
   - Dashboard (project list)
   - Project detail (with discovered documents)
   - Project edit (name, domain, description)

4. Create import workflow
   - Display discovered files
   - Select files to import
   - Run import → sync to SourceDocument

**Files to create/modify:**
- `ki_knowledge/services/discovery.py` (new)
- `ki_knowledge/django_site/infosite_models.py` (update)
- `ki_knowledge/django_site/infosite_views.py` (expand)
- `ki_knowledge/django_site/templates/infosite/project_list.html` (new)
- `ki_knowledge/django_site/templates/infosite/project_detail.html` (new)

**Test case:**
- Domain: `anthro`
- Working title: `sstk`
- Source directory: `md/anthro/sstk/bg/` (symlinked)
- Expected files: ~8 directories with .md content

---

### Phase 2: Generation & Versioning

**Goals:**
- Run InfoSiteGenerator from web UI
- Create output in `data_out/<domain>/<working_title>/`
- Track generation status and versions

**Tasks:**
- Integrate `ki_knowledge.infosite.InfoSiteGenerator`
- Add generation workflow view
- Track output status in DB
- Implement version management

---

### Phase 3: AI Refinement

**Goals:**
- Enhance generated markdown with AI
- Support multiple refinement modes

**Tasks:**
- Integrate ki-core AIClient
- Implement refinement UI
- Store refined versions

---

### Phase 4: Advanced Features

**Goals:**
- Link to knowledge blocks
- Graph-based navigation
- Version history & diff viewing

**Tasks:**
- Create knowledge block linker
- Build graph visualization
- Implement diff viewer

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
- InfoSiteGenerator service (ki_knowledge.infosite)
- AI refinement modes (Improve, Restructure, Summarize)

### 🚧 In Progress (Phase 1)
- Document auto-discovery service
- Project management views
- Document display in UI
- Import workflow integration

### ⏳ Pending (Phase 2+)
- Generation workflow
- Output preview
- Version tracking
- Knowledge block linking
- Advanced versioning

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
