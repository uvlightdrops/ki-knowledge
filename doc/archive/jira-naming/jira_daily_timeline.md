---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: "2026-09-02 07"
updated: "2026-11-08 00"
update_reason: "Veraltete Jira-Timeline und unbelegte Aussage gekennzeichnet"
status: archived
---

# Deprecated Jira naming: daily timeline

> Historical note: the Jira-specific timeline is legacy, and the claim below
> that it already covers arbitrary source types is not established.

This legacy filename remains for compatibility. The timeline feature is now datasource-agnostic and documented here:

- [daily_timeline.md](../../features/archiv/daily_timeline.md)
- [knowledge_retrieval.md](../../features/knowledge_retrieval.md)

## Status

The daily timeline aggregates timestamped knowledge into daily summaries. It is not tied to Jira-only data and can be used with any imported source that has timestamps and content in the knowledge cache.

## Example

```bash
python examples/jira_daily_timeline.py
```

This remains valid, but the capability is designed as general temporal analysis, not Jira-specific reporting.
