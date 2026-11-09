---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-09 22"
updated: "2026-11-08 00"
update_reason: "Jira-spezifischen Graphpfad ins Bereichsarchiv verschoben"
status: archived
semantic_blocks:
  - purpose
  - capabilities
  - example
  - scope
  - references
relations:
  - target: README.md
    type: parent
    reason: "Bereichsarchiv der Fachfunktionen"
---

# Graph Explorer

> **Legacy:** Der hier beschriebene Jira-spezifische Graphpfad ist veraltet.
> Jira soll künftig ein gleichberechtigtes Eingabe-/Importformat sein; eine
> quellenübergreifende Nachfolge ist damit nicht als umgesetzt behauptet.

<a id="purpose"></a>
## Purpose [purpose]

Build and inspect the Jira issue graph using the Jira cache. Other graph
implementations exist, but this page does not establish that this explorer
combines all imported KnowledgeStore sources.

<a id="features"></a>
<a id="capabilities"></a>
## Features [capabilities]

- rebuild the relationship graph from the cache
- inspect node and edge counts
- show neighbors or connected entities for a selected item
- export Cypher-compatible query statements for external graph tools

<a id="example-usage"></a>
<a id="example"></a>
## Example usage [example]

The script can import Jira CSV issues and rebuilds the Jira graph:

```bash
# show graph statistics
python examples/jira_graph_explorer.py

# inspect one issue and its neighbours
python examples/jira_graph_explorer.py "ISSUE-123"
```

For an optional Cypher export, the script reads `JIRA_GRAPH_CYPHER_PATH`.

<a id="design-note"></a>
<a id="scope"></a>
## Design note [scope]

The Jira graph and the graph built from KnowledgeStore relations are distinct
paths. Source-independent graph exploration is a possible direction, not a
claim established by this Jira example.

<a id="see-also"></a>
<a id="references"></a>
## See also [references]

- [knowledge_retrieval.md](../knowledge_retrieval.md)
- [hybrid_search.md](hybrid_search.md)
- [support_chat.md](../support_chat.md)
