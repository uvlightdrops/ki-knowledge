---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 01"
update_reason: "Jira-Beispiele und frühere Arbeitsabläufe aus der Retrieval-Übersicht archiviert"
status: archived
semantic_blocks:
  - jira-retrieval
  - jira-graph
  - jira-chat-example
  - jira-timeline
  - earlier-workflows
relations:
  - target: README.md
    type: parent
    reason: "Archiv der Fachfunktionen"
  - target: ../knowledge_retrieval.md
    type: reference
    reason: "Aktuelle Einordnung von Retrieval und Domain-Chat"
  - target: ../support_chat.md
    type: reference
    reason: "Domain-Chat und Verweis auf früheres Jira-Beispiel"
---

# Retrieval: frühere Jira-Pfade

Diese Abschnitte wurden aus der [Retrieval-Übersicht](../knowledge_retrieval.md)
ausgelagert. Sie dokumentieren alte Jira-spezifische Pfade und frühere Ideen,
nicht das neue Wissensmodell. Suche, Retrieval und Chat bleiben gewünschte
Funktionen; Jira ist künftig ein gleichberechtigtes Eingabeformat.

<a id="jira-retrieval"></a>
## Jira-Retrieval [jira-retrieval]

The Jira retrieval service combines lexical and semantic matching over its
issue cache. The example requires at least one query and can refresh the
cache and build embeddings:

```bash
python examples/jira_hybrid_search.py "search terms"
```

Typical outputs:
- best keyword matches
- best semantic matches
- combined ranking scores
- a tuning view for search quality

See: [hybrid_search.md](hybrid_search.md)

<a id="jira-graph"></a>
## Jira-Graph [jira-graph]

The Jira graph explorer inspects issue neighbours in a graph built from its
Jira cache. The example rebuilds that graph; it is not a read-only overview of
all imported sources.

```bash
python examples/jira_graph_explorer.py
```

See: [graph_explorer.md](graph_explorer.md)

<a id="jira-chat-example"></a>
## Jira-Chatbeispiel [jira-chat-example]

The older Jira-specific example is:

```bash
python examples/jira_support_chat.py
```

That example uses a Jira CSV/cache and its own Ollama integration; it is not
the current Domain Chat entry point.

<a id="jira-timeline"></a>
## Jira-Timeline [jira-timeline]

The current Jira service and example aggregate Jira issues by day. The
example imports issues into the cache; it does not demonstrate a timeline for
arbitrary timestamped sources.

```bash
python examples/jira_daily_timeline.py
```

See: [daily_timeline.md](daily_timeline.md)

<a id="earlier-workflows"></a>
## Frühere Ablaufideen [earlier-workflows]

The following are exploratory ideas, not a verified end-to-end workflow
across the separate stores.

### Workflow 1: Explore a new domain

1. import new sources
2. run hybrid search to understand topical coverage
3. inspect graph relationships
4. ask grounded questions in support chat

### Workflow 2: Quality checks

1. search the current domain with different terms
2. inspect graph neighborhoods
3. compare timeline trends
4. refine input sources if the coverage is weak

### Workflow 3: Operational monitoring

1. run timeline summaries across a time window
2. identify patterns in activity or content density
3. use support chat to answer follow-up questions with evidence
