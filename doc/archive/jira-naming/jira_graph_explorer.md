---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: "2026-09-02 07"
updated: "2026-11-08 00"
update_reason: "Veralteten Jira-Graphpfad und unbelegte Aussage gekennzeichnet"
status: archived
---

# Deprecated Jira naming: graph explorer

> Historical note: the Jira-specific graph explorer is legacy, and the claim
> below that it covers all imported source types is not established.

This legacy file name remains for compatibility. The underlying functionality is datasource-agnostic and is documented here as the canonical graph feature:

- [graph_explorer.md](../../features/archiv/graph_explorer.md)
- [knowledge_retrieval.md](../../features/knowledge_retrieval.md)

## Status

The graph explorer reads from the cached knowledge graph and can visualize relationships generated from imported Markdown, PDF, ontology, Jira or other structured source material.

## Example

```bash
python examples/jira_graph_explorer.py AE-123
```

This still works, but the feature is no longer treated as Jira-specific.
