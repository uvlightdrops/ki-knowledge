---
title: "InfoSite Architecture Analysis and Refactoring Plan"
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
purpose: "Historical analysis and proposed architecture for the InfoSite presentation pipeline."
created: "2026-09-02T18:17:58+02:00"
updated: "2026-11-08 00"
update_reason: "Jira-Implementierungen als Legacy eingeordnet"
status: archived
semantic_blocks:
  - current-state
  - core-concepts
  - django-architecture
  - implementation-roadmap
  - design-patterns
  - next-steps
relations:
  - target: "SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md"
    type: reference
    reason: "Führendes Konzept für Quellenaufnahme"
---

# Infosite Architecture Analysis & Refactoring Plan

> Jira-spezifische Implementierungen gehören zum Legacy-Bestand. Jira soll
> künftig ein gleichberechtigtes Eingabe-/Importformat sein; das ist ein Ziel,
> keine Aussage über eine bereits abgeschlossene Umstellung. Analysis & Refactoring Plan

> Historical architecture plan. The leading source-intake/UI document is
> [Source Workspace and Workflow Concept](SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md).
> Its shared inventory model takes precedence over separate intake screens
> proposed here.

## Current State Assessment [current-state]

### Problem
- Admin models created (InfoSiteProject, SourceDocument) but Django views/URLs not architected
- Input documents in the configured domain markdown directory are not auto-discovered
- Architecture is "arbitrary" - models without clear integration with rest of Django site
- Logic similar to "data sources" but not unified

### Data Structure (Example: anthro/sstk)
```
~/dev_data/ki-knowledge/
├── anthro/
│   └── md/
│       ├── prompt-library/      (existing)
│       └── sstk/                (infosite working title)
│           └── bg/              (symlink to source documents)
│           ├── DreigliederungAlsLeitbild/
│           ├── Framework_Diagnosen/
│           ├── IntegralePsychologie/
│           └── ... (8 more directories with .md files)
```

---

## Core Concepts (from docs) [core-concepts]

### InfoSite vs Data Sources
- **Data Sources**: Import, manage raw source documents (Markdown, PDF, OWL, Jira)
- **InfoSite**: Transform source docs → structured knowledge presentation (markdown output)

### InfoSite Output Structure
```
<data_root>/<domain>/output/<working_title>/
├── index.md
├── overview.md
├── metadata.yml
├── _originals/v1-original/
└── topics/
```

### InfoSite Workflow (Phase 1)
1. **Discovery**: Auto-find source documents in `<domain>/md/<working_title>/`
2. **Import**: Scan & track found files in Django DB (SourceDocument model)
3. **Generation**: Convert to structured markdown in output dir
4. **Versioning**: Store original as v1-original baseline
5. **AI Refinement** (later): Enhance with LLM assistance

---

## Django Architecture (Current vs Desired) [django-architecture]

### Current State (Incorrect)
```
urls.py
├── admin/                           ← Admin models only
├── infosite/dashboard/              ← Web UI but orphaned
└── ... (other routes)

Models (infosite_models.py)
├── InfoSiteProject                  ← Empty, no auto-discovery
└── SourceDocument                   ← Not linked to file system
```

### Desired State (Unified)
```
urls.py
├── admin/                                  ← Admin (project mgmt)
├── data-sources/                          ← Data source browsing
│   ├── list/
│   └── import/
├── infosite/
│   ├── dashboard/                         ← Project list
│   ├── project/<id>/
│   │   ├── documents/                     ← Auto-discovered sources
│   │   ├── import/                        ← Run import workflow
│   │   ├── generate/                      ← Generate infosite
│   │   ├── refine/                        ← AI refinement
│   │   └── preview/                       ← Preview generated output
│   └── status/                            ← Generation status
└── ... (other routes)

Services (unified)
├── SourceDiscovery                        ← Find files in filesystem
│   ├── find_data_sources()                ← For Data Sources
│   └── find_infosite_documents()          ← For Infosite
├── InfoSiteGenerator                      ← Generate output markdown
├── DocumentImporter                       ← Track in DB
└── AIRefiner                              ← Enhance content
```

---

## Implementation Roadmap [implementation-roadmap]

### Phase 1: Architecture & Auto-Discovery Ready to implement
- [ ] Create `DocumentDiscoveryService` (unified file finder)
- [ ] Implement `find_infosite_documents(domain, working_title)` 
- [ ] Add InfoSite project views (list, detail, manage)
- [ ] Link UI to auto-discovered documents
- [ ] Update models to track source file paths

### Phase 2: Import & Generation (Next)
- [ ] Implement file import workflow
- [ ] Create generator service integration
- [ ] Track generation status in DB

### Phase 3: AI Refinement (Later)
- [ ] Integrate ki-core AIClient
- [ ] Implement refinement modes

### Phase 4: Versioning (Later)
- [ ] Track version history
- [ ] Implement diff viewing

---

## Key Design Patterns [design-patterns]

### 1. Service Layer (not views directly)
- `DocumentDiscoveryService` - Find files
- `InfoSiteGeneratorService` - Run generator
- `SourceImporterService` - Track in DB

### 2. URL Hierarchy (mirrors Django structure)
```python
path("infosite/", include([
    path("dashboard/", views.infosite_dashboard),
    path("project/<int:project_id>/", views.project_detail),
    path("project/<int:project_id>/documents/", views.project_documents),
    path("project/<int:project_id>/import/", views.project_import),
]))
```

### 3. Database Synchronization
- Auto-discovery finds files
- Import workflow syncs to DB (SourceDocument)
- UI shows linked documents with import status

---

## Next Steps [next-steps]

1. **Create DiscoveryService** (reusable for data sources + infosite)
2. **Test with anthro/sstk** (find documents, display in UI)
3. **Implement project views** (detail, manage, import)
4. **Link UI to models** (show discovered documents)
5. **Add generation workflow** (import → generate → versioning)
