---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 01"
update_reason: "Überholte Retrieval- und Pipelineaussagen aus dem Systemüberblick ausgelagert"
status: archived
semantic_blocks:
  - retrieval
  - pipeline
relations:
  - target: README.md
    type: parent
    reason: "Architekturarchiv"
  - target: ../SYSTEM_OVERVIEW.md
    type: reference
    reason: "Herkunft der früheren Architekturabschnitte"
---

# Frühere Datenflüsse

Diese Abschnitte stammen aus dem
[Systemüberblick](../SYSTEM_OVERVIEW.md). Sie sind historische Darstellungen,
keine aktuelle Architektur oder fertig implementierte End-to-End-Pipeline.
Das [fachliche Konzept](../KI-KNOWLEDGE-KONZEPT.md) grenzt Zielbild und
bisherige Arbeitswege voneinander ab.

<a id="retrieval"></a>
## Frühere Retrieval-Einordnung [retrieval]

Die folgende frühere Zusammenfassung erklärte quellenübergreifendes Retrieval
als implementiert, belegte es aber nur mit Jira-Beispielen. Jira-Sonderpfade
sind Legacy; Suche, Retrieval und Chat als Produktfunktionen bleiben gewünscht.
Der separate Domain-Chat wird durch diese Einordnung nicht pauschal verworfen.

> **Knowledge Retrieval** (Search & Analysis)
>
> **Purpose:** Find, analyze, and query knowledge across sources
>
> **Features:** Hybrid search (keyword + semantic); knowledge graph explorer;
> RAG-based semantic chat; timeline/temporal analysis.
>
> **Key Files:** `examples/jira_hybrid_search.py`,
> `examples/jira_graph_explorer.py`, `examples/jira_support_chat.py`,
> `examples/jira_daily_timeline.py`.
>
> **Status:** Implemented.

<a id="pipeline"></a>
## Frühere Pipelinezeichnung [pipeline]

Die Zeichnung suggerierte einen einheitlichen Ablauf und setzte strukturelle
Zerlegung mit semantischem Verständnis gleich. Tatsächlich sind die
vorhandenen Wege getrennt; zum Beispiel ist InfoSite Import Control eine
synchrone Statusübergabe und keine Inhaltsaufnahme.

```text
1. SOURCE DOCUMENT
   └── <domain>/md/<working_title>/*.md
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
