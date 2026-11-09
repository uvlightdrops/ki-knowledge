---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: "2026-09-02 07"
updated: "2026-11-08 00"
update_reason: "Veralteten Jira-Suchpfad und unbelegte Aussage gekennzeichnet"
status: archived
---

# Deprecated Jira naming: hybrid search

> Historical note: the Jira-specific search is legacy, and the claim below
> that this path already covers arbitrary source types is not established.

This legacy file name still exists for compatibility, but the feature it describes is now datasource-agnostic.

The current, canonical documentation is:

- [hybrid_search.md](../../features/archiv/hybrid_search.md)
- [knowledge_retrieval.md](../../features/knowledge_retrieval.md)

## Status

The hybrid-search logic operates on the cached knowledge layer and is not tied to Jira data alone. It can be used with:

- Markdown-derived records
- PDF extracted content
- OWL/ontology data
- Jira exports
- any future source integrated into the knowledge cache

## Example

```bash
python examples/jira_hybrid_search.py
```

This call remains valid, but the feature is now treated as a general retrieval capability rather than a Jira-only utility.
