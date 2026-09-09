# Deprecated Jira naming: support chat

The older Jira-specific name remains only for compatibility. The canonical documentation is now source-agnostic and lives here:

- [support_chat.md](support_chat.md)
- [knowledge_retrieval.md](knowledge_retrieval.md)

## Status

Support chat is built on retrieved context from the active knowledge layer. It can answer questions grounded in Markdown, PDF, OWL, Jira, or any other source that has been ingested into the cache or vector store.

## Example

```bash
python examples/jira_support_chat.py
```

The call still works, but the feature is no longer specific to Jira data.

