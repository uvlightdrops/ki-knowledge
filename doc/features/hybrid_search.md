# Hybrid Search

## Purpose

Search across all imported source types with a mix of lexical scan and semantic similarity. The same flow works for Markdown, PDFs, OWL data, Jira exports, or any cached source that is indexed into the knowledge store.

## What it does

- queries multiple natural-language and keyword searches
- combines lexical scoring with semantic similarity
- uses Ollama embeddings when available, with a local fallback for lighter environments
- compares results side by side for tuning and debugging

## Typical inputs

- `KNOWLEDGE_DATA_ROOT`
- `KNOWLEDGE_CACHE_DB`
- `KNOWLEDGE_EMBED_MODEL`
- `OLLAMA_BASE_URL`
- `KNOWLEDGE_CACHE_REFRESH` or equivalent cache refresh setting

## Example

```bash
python examples/jira_hybrid_search.py
```

This example still uses the existing Jira cache path for compatibility, but the logic is not Jira-specific: it can be reused for any source-backed cache.

## Best use cases

- find conceptually similar records quickly
- compare keyword vs semantic ranking
- build a high-recall first pass before deeper analysis
- inspect which source type contributes the best matches

## See also

- [knowledge_retrieval.md](knowledge_retrieval.md)
- [graph_explorer.md](graph_explorer.md)
- [support_chat.md](support_chat.md)
- [daily_timeline.md](daily_timeline.md)
