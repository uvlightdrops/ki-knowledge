---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-02 07"
updated: "2026-11-08 01"
update_reason: "Jira-Altpfade und unbestätigte Ablaufideen ins Facharchiv ausgelagert"
status: draft
semantic_blocks:
  - feature-index
  - hybrid-retrieval
  - graph-analysis
  - domain-chat
  - timeline
  - architecture-boundaries
  - configuration
  - workflows
  - references
relations:
  - target: archiv/RETRIEVAL_JIRA_ALTPFADE.md
    type: reference
    reason: "Ausgelagerte Jira-Beispiele und frühere Ablaufideen"
  - target: ../architecture/KI-KNOWLEDGE-KONZEPT.md
    type: reference
    reason: "Fachliches Zielbild und Grenzen der bisherigen Implementierung"
  - target: support_chat.md
    type: reference
    reason: "Separater bestehender Domain-Chat"
---

# Knowledge Retrieval & Analysis

**Gewünschte Funktionen:** Knowledge Retrieval, Suche und Chat sollen
weiterentwickelt werden. Ihre fachliche Ausgestaltung und die künftigen
quellenübergreifenden Wege sind noch zu erarbeiten; bestehende Implementierungen
oder die folgenden historischen Beispiele sind kein vollständiger Nachweis
dieses Zielbilds.

> **Legacy-Grenze:** Die [archivierten Jira-spezifischen Pfade](archiv/RETRIEVAL_JIRA_ALTPFADE.md)
> sind veraltet. Jira ist künftig als gleichberechtigtes Eingabe-/
> Importformat vorgesehen; der separate Domain-Chat ist damit nicht pauschal
> als veraltet eingeordnet.

This landing page groups retrieval and analysis features. Their names describe
broader ideas, but they do not all use the same store or support every source:
the examples and service for hybrid search, timeline and graph exploration
in the archive are Jira-specific. Domain Chat has a separate KnowledgeStore-based
path. The older feature descriptions must not be read as proof of
source-independent functionality.

<a id="quick-reference"></a>
<a id="feature-index"></a>
## Quick Reference [feature-index]

| Feature | Document | Purpose |
|---|---|---|
| Hybrid search | [hybrid_search.md](archiv/hybrid_search.md) | Jira-Legacy; Suche als Funktion bleibt gewünscht |
| Graph explorer | [graph_explorer.md](archiv/graph_explorer.md) | Jira-Legacy; kein allgemeiner Graphnachweis |
| Support chat | [support_chat.md](support_chat.md) | Separater Domain-Chat; Jira-Beispiele sind Legacy |
| Daily timeline | [daily_timeline.md](archiv/daily_timeline.md) | Jira-Legacy |

---

<a id="1-retrieval-and-discovery"></a>
<a id="hybrid-retrieval"></a>
## 1. Retrieval and Discovery [hybrid-retrieval]

Die quellenübergreifende Suche nach Wissensblöcken ist ein
[Vorschlag für das neue Modell](../architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md#search-proposal).
Der [frühere Jira-Suchpfad](archiv/RETRIEVAL_JIRA_ALTPFADE.md#jira-retrieval)
ist dafür kein Implementierungsnachweis.

---

<a id="2-graph-based-understanding"></a>
<a id="graph-analysis"></a>
## 2. Graph-Based Understanding [graph-analysis]

Die Auswertung von Beziehungen ist für das neue Wissensmodell noch zu
gestalten. Der [frühere Jira-Graphpfad](archiv/RETRIEVAL_JIRA_ALTPFADE.md#jira-graph)
betrachtet nur Jira-Issues.

---

<a id="3-grounded-qa"></a>
<a id="domain-chat"></a>
## 3. Grounded Q&A [domain-chat]

Domain Chat uses indexed KnowledgeStore records scoped to the active domain.
See [support_chat.md](support_chat.md) for indexing and coverage requirements.
It is a separate workflow from the [older Jira example](archiv/RETRIEVAL_JIRA_ALTPFADE.md#jira-chat-example).

---

<a id="4-temporal-summaries"></a>
<a id="timeline"></a>
## 4. Temporal Summaries [timeline]

Die [frühere Jira-Timeline](archiv/RETRIEVAL_JIRA_ALTPFADE.md#jira-timeline)
belegt keine allgemeine zeitliche Auswertung beliebiger Quellen.

---

<a id="scope-and-architecture"></a>
<a id="architecture-boundaries"></a>
## Scope and architecture [architecture-boundaries]

Jira search, timeline and graph operations are grouped in
`ki_knowledge/services/jira_retrieval.py`. Domain Chat reads indexed
KnowledgeStore records via `ki_knowledge/django_site/support_chat.py`.
Extending the former to other source types would require separate evidence and
design; it is not implied by the common terminology.

---

<a id="environment-setup"></a>
<a id="configuration"></a>
## Configuration [configuration]

Use the [project configuration guide](../guides/YAML_CONFIG_SYSADMIN.md)
for the shared configuration layers. The older Jira examples also contain
Jira-specific environment overrides; inspect the relevant example before use.

---

<a id="typical-workflows"></a>
<a id="workflows"></a>
## Typical workflows [workflows]

Ein [neuer beispielhafter Arbeitsweg](../architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md#example-workflow)
beschreibt das Zielbild, keine durchgängige Implementierung. Die
[früheren Ablaufideen](archiv/RETRIEVAL_JIRA_ALTPFADE.md#earlier-workflows)
über getrennte Stores sind archiviert.

---

<a id="see-also"></a>
<a id="references"></a>
## See also [references]

- [knowledge_blocks.md](knowledge_blocks.md)
- [pdf_batch_import.md](pdf_batch_import.md)
- [SYSTEM_OVERVIEW.md](../architecture/SYSTEM_OVERVIEW.md)
