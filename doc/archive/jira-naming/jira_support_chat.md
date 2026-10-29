# Deprecated Jira naming: support chat

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
