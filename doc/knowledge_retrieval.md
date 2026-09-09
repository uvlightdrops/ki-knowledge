# Knowledge Retrieval & Analysis

This landing page groups the source-agnostic discovery and analysis features of the knowledge stack. The same search, graph and chat patterns work regardless of whether content came from Markdown, PDFs, OWL, Jira exports, or other imported sources.

## Quick Reference

| Feature | Document | Purpose |
|---|---|---|
| Hybrid search | [hybrid_search.md](hybrid_search.md) | Combine keyword and semantic retrieval |
| Graph explorer | [graph_explorer.md](graph_explorer.md) | Inspect relationships between entities and concepts |
| Support chat | [support_chat.md](support_chat.md) | Ask grounded questions over the loaded knowledge |
| Daily timeline | [daily_timeline.md](daily_timeline.md) | Summarize chronology and trends across cached data |

---

## 1. Retrieval and Discovery

The hybrid search flow is the primary entry point for source-agnostic retrieval. It combines lexical search with semantic matching so the system can find both literal and conceptually similar results.

```bash
python examples/jira_hybrid_search.py
```

Typical outputs:
- best keyword matches
- best semantic matches
- combined ranking scores
- a tuning view for search quality

See: [hybrid_search.md](hybrid_search.md)

---

## 2. Graph-Based Understanding

The graph explorer answers questions like “which entities are connected?” and “what clusters or neighborhoods exist around this topic?” It works for any source that creates relationship edges in the graph store.

```bash
python examples/jira_graph_explorer.py
```

See: [graph_explorer.md](graph_explorer.md)

---

## 3. Grounded Q&A

The support chat is a retrieval-augmented assistant for the active knowledge base. It is designed to answer from indexed content rather than from generic model memory.

```bash
python examples/jira_support_chat.py
```

See: [support_chat.md](support_chat.md)

---

## 4. Temporal Summaries

Timeline analysis aggregates timestamped records by day to reveal patterns, trends, or repeated themes across the imported domain.

```bash
python examples/jira_daily_timeline.py
```

See: [daily_timeline.md](daily_timeline.md)

---

## Scope and architecture

These features are intentionally datasource-agnostic. They operate on the cached and indexed knowledge layer rather than on a single source implementation such as Jira. That means the same retrieval and analysis flows can be reused when the project ingests Markdown, PDF, OWL, Jira or any future source type.

---

## Environment setup

```bash
# ~/.env or export these:

KNOWLEDGE_DATA_ROOT=~/dev_data/ki-knowledge
KNOWLEDGE_CACHE_DB=~/.ki_cache.sqlite
KNOWLEDGE_GRAPH_DB=~/.ki_graph.sqlite
KNOWLEDGE_EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Typical workflows

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

---

## See also

- [knowledge_blocks.md](knowledge_blocks.md)
- [pdf_batch_import.md](pdf_batch_import.md)
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
