# Support Chat

## Purpose

Provide grounded Q&A over imported knowledge by combining retrieval with LLM response generation. The implementation is source-agnostic: it answers from the current knowledge index, regardless of whether the content came from Markdown, PDF, OWL, Jira, or other data sources.

## What it does

- retrieves relevant passages or document chunks
- ranks them by relevance
- grounds the assistant answer in the fetched context
- keeps the conversation history for follow-up questions

## Example

```bash
python examples/jira_support_chat.py
```

This script still uses the Jira-compatible example name for historical reasons, but the chat flow is designed to work with any indexed knowledge source.

## Best use cases

- ask domain questions in natural language
- get brief, evidence-based answers from imported content
- compare multiple source types when troubleshooting or summarizing
- build a conversational layer over the knowledge base without coupling to one source system

## See also

- [knowledge_retrieval.md](knowledge_retrieval.md)
- [hybrid_search.md](hybrid_search.md)
- [graph_explorer.md](graph_explorer.md)
