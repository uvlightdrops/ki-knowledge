# Deprecated Jira naming: hybrid search

This legacy file name still exists for compatibility, but the feature it describes is now datasource-agnostic.

The current, canonical documentation is:

- [hybrid_search.md](hybrid_search.md)
- [knowledge_retrieval.md](knowledge_retrieval.md)

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

