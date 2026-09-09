# Deprecated Jira naming: graph explorer

This legacy file name remains for compatibility. The underlying functionality is datasource-agnostic and is documented here as the canonical graph feature:

- [graph_explorer.md](graph_explorer.md)
- [knowledge_retrieval.md](knowledge_retrieval.md)

## Status

The graph explorer reads from the cached knowledge graph and can visualize relationships generated from imported Markdown, PDF, ontology, Jira or other structured source material.

## Example

```bash
python examples/jira_graph_explorer.py AE-123
```

This still works, but the feature is no longer treated as Jira-specific.
