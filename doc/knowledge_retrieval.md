# Knowledge Retrieval & Analysis

This page provides an overview of the tools available for searching, analyzing, and exploring imported knowledge.

## Quick Reference

| Task | Tool | Purpose |
|------|------|---------|
| Find Jira issues by keywords or meaning | [`examples/jira_hybrid_search.py`](../examples/jira_hybrid_search.py) | Keyword + semantic search |
| Explore Jira graph relationships | [`jira_graph_explorer.md`](jira_graph_explorer.md) | Inspect cached Jira graph |
| Chat with grounded answers | [`jira_support_chat.md`](jira_support_chat.md) | RAG-based Q&A |
| Timeline & trending topics | [`jira_daily_timeline.md`](jira_daily_timeline.md) | Temporal summaries |

---

## 1. Hybrid Search

**Search across all imported sources** using both keyword matching and semantic similarity.

```bash
python examples/jira_hybrid_search.py
```

**Best for:**
- Finding similar documents quickly
- Comparing keyword vs. semantic results
- Tuning search weights
- Works with any cached data (CSV, Markdown, PDFs, etc.)

See: `examples/jira_hybrid_search.py`

---

## 2. Knowledge Graph Explorer

**Build and inspect the relationship graph** connecting your knowledge sources.

```bash
python examples/jira_graph_explorer.py
```

**Best for:**
- Understanding how concepts relate
- Finding neighbors and indirect connections
- Exporting Cypher queries for analysis
- Visualizing domain structure

See: [`jira_graph_explorer.md`](jira_graph_explorer.md)

---

## 3. Semantic Chat (RAG)

**Ask questions grounded in your knowledge sources** using Retrieval-Augmented Generation.

```bash
python examples/jira_support_chat.py
```

**Best for:**
- Natural language Q&A
- Sourced answers with citations
- Multi-turn conversations
- Domain-specific knowledge bases

See: [`jira_support_chat.md`](jira_support_chat.md)

---

## 4. Cache Timeline

**Analyze temporal patterns** and extract daily summaries from timestamped data.

```bash
python examples/jira_daily_timeline.py
```

**Best for:**
- Tracking progress over time
- Identifying trending topics
- Creating event summaries
- Narrative reconstruction

See: [`jira_daily_timeline.md`](jira_daily_timeline.md)

---

## Environment Setup

All tools use the same base configuration:

```bash
# ~/.env or export these:

# Data location
KICLI_DATA_ROOT=~/dev_data/ki-knowledge

# Cache and graph databases
KI_CACHE_DB=~/.ki_cache.sqlite
KI_GRAPH_DB=~/.ki_graph.sqlite

# Embeddings (optional, fallback to TF-IDF)
KI_EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Common Workflows

### Workflow 1: Explore a New Domain

1. Import sources with `knowledge_block_import.py` or the API
2. Run `jira_hybrid_search.py` to understand Jira content
3. Use `jira_graph_explorer.py` to inspect structure
4. Ask questions with `jira_support_chat.py`

### Workflow 2: Generate Insights

1. Import domain data
2. Use `jira_daily_timeline.py` to find patterns
3. Use `jira_support_chat.py` to dig deeper
4. Export results via `jira_graph_explorer.py`

### Workflow 3: Quality Control

1. Run `jira_hybrid_search.py` with test queries
2. Review top results
3. Inspect graph with `jira_graph_explorer.py`
4. Refine domain or re-import if needed

---

## Performance Tips

- **Hybrid Search**: Keyword search is fast; embeddings slower but more accurate
- **Graph Explorer**: First run rebuilds graph; subsequent runs are cached
- **Timeline**: Best with chronologically sorted data
- **Semantic Chat**: Provide good context; multi-turn builds history

---

## Troubleshooting

**Search returns poor results?**
- Check data was imported with `knowledge_block_import.py` or `/api/knowledge/import`
- Try `jira_hybrid_search.py` with different keywords
- Increase `top_n` parameter in queries

**Graph shows no relationships?**
- Verify sources were processed (check cache)
- Some sources (PDF text) don't auto-create relationships
- Run `jira_graph_explorer.py` to rebuild

**Chat answers are generic?**
- Provide more context in questions
- Use specific domain terminology
- Check embeddings are working (`OLLAMA_BASE_URL`)

---

## See Also

- [`knowledge_blocks.md`](knowledge_blocks.md) – Import and knowledge artifacts
- [`pdf_batch_import.md`](pdf_batch_import.md) – PDF batch processing
- [`jira_support_chat.md`](jira_support_chat.md) – Detailed RAG guide
