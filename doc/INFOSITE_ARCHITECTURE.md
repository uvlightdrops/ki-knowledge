# Infosite Architecture Analysis & Refactoring Plan

## Current State Assessment

### 🎯 Problem
- Admin models created (InfoSiteProject, SourceDocument) but Django views/URLs not architected
- Input documents in `datadir/md/<domain>/<working_title>` not auto-discovered
- Architecture is "arbitrary" - models without clear integration with rest of Django site
- Logic similar to "data sources" but not unified

### 📊 Data Structure (Example: anthro/sstk)
```
~/dev_data/ki-knowledge/md/
├── anthro/
│   ├── prompt-library/          (existing)
│   └── sstk/                    (infosite working title)
│       └── bg/                  (symlink to source documents)
│           ├── DreigliederungAlsLeitbild/
│           ├── Framework_Diagnosen/
│           ├── IntegralePsychologie/
│           └── ... (8 more directories with .md files)
```

---

## Core Concepts (from docs)

### InfoSite vs Data Sources
- **Data Sources**: Import, manage raw source documents (Markdown, PDF, OWL, Jira)
- **InfoSite**: Transform source docs → structured knowledge presentation (markdown output)

### InfoSite Output Structure
```
<data_root>/data_out/<domain>/<working_title>/
├── index.md
├── overview.md
├── metadata.yml
├── _originals/v1-original/
└── topics/
```

### InfoSite Workflow (Phase 1)
1. **Discovery**: Auto-find source documents in `md/<domain>/<working_title>/`
2. **Import**: Scan & track found files in Django DB (SourceDocument model)
3. **Generation**: Convert to structured markdown in output dir
4. **Versioning**: Store original as v1-original baseline
5. **AI Refinement** (later): Enhance with LLM assistance

---

## Django Architecture (Current vs Desired)

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

## Implementation Roadmap

### Phase 1: Architecture & Auto-Discovery ✅ Ready to implement
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

## Key Design Patterns

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

## Next Steps

1. **Create DiscoveryService** (reusable for data sources + infosite)
2. **Test with anthro/sstk** (find documents, display in UI)
3. **Implement project views** (detail, manage, import)
4. **Link UI to models** (show discovered documents)
5. **Add generation workflow** (import → generate → versioning)

