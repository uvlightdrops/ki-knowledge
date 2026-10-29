# Graph Explorer

## Purpose

Build and inspect the relationship graph that connects imported knowledge. The graph can be created from source-backed records, Markdown-derived blocks, PDF content, ontology links, or structured exports.

## Features

- rebuild the relationship graph from the cache
- inspect node and edge counts
- show neighbors or connected entities for a selected item
- export Cypher-compatible query statements for external graph tools

## Example usage

```bash
# show graph statistics
python examples/jira_graph_explorer.py

# inspect one entity and its neighbours
python examples/jira_graph_explorer.py --entity-id "some-entity-key"

# export Cypher snippets
python examples/jira_graph_explorer.py --export-cypher
```

## Design note

This feature was originally shaped around Jira CSV data, but the graph layer is now treated as a datasource-agnostic knowledge layer. Any imported source that contributes relationships can participate in the graph.

## See also

- [knowledge_retrieval.md](knowledge_retrieval.md)
- [hybrid_search.md](hybrid_search.md)
- [support_chat.md](support_chat.md)
