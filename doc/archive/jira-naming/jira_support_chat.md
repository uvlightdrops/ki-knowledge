---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: "2026-09-02 07"
updated: "2026-11-08 00"
update_reason: "Veraltetes Jira-Chatbeispiel gekennzeichnet"
status: archived
---

# Deprecated Jira naming: support chat

> Historical note: the Jira-specific example is legacy and is not the current
> domain-scoped KnowledgeStore chat.

The older Jira-specific name remains only for compatibility. The canonical documentation is now source-agnostic and lives here:

- [support_chat.md](../../features/support_chat.md)
- [knowledge_retrieval.md](../../features/knowledge_retrieval.md)

## Status

Domain Chat is built on current embedded KnowledgeStore records scoped to the
active domain, including Nextcloud and contributions. Import alone is not enough:
records also need current vectors. The legacy Jira GET redirects to the single
Chat page; Jira POSTs use that same grounded answering path. See
[support_chat.md](../../features/support_chat.md) for coverage, conversation and compatibility limits.

## Example

```bash
python examples/jira_support_chat.py
```

The call still works, but the feature is no longer specific to Jira data.
