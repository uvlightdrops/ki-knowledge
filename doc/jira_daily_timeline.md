# Deprecated Jira naming: daily timeline

This legacy filename remains for compatibility. The timeline feature is now datasource-agnostic and documented here:

- [daily_timeline.md](daily_timeline.md)
- [knowledge_retrieval.md](knowledge_retrieval.md)

## Status

The daily timeline aggregates timestamped knowledge into daily summaries. It is not tied to Jira-only data and can be used with any imported source that has timestamps and content in the knowledge cache.

## Example

```bash
python examples/jira_daily_timeline.py
```

This remains valid, but the capability is designed as general temporal analysis, not Jira-specific reporting.

