# Domain Chat

## Purpose

The knowledge submenu has one **Chat**, at `/knowledge/chat/support/`
(`support-chat`). It converses with the texts and extracted knowledge of the
active domain, not a free-standing general chat. The provider and model come
from `llm.default_provider` / `llm.providers.*` via `ki_knowledge.llm_provider`;
provider selection remains in Settings.

## What it does

- Retrieves KnowledgeStore records using semantic similarity and the active
  domain's registered **source IDs**. All source types are included by default,
  including `nextcloud_markdown`, custom source types and domain-owned
  contributions. Optional source filters do not widen unknown types to all.
- Uses current vectors of `knowledge.embed_model` (or `KNOWLEDGE_EMBED_MODEL`).
  Embeddings remain on the configured Ollama endpoint, independently of the chat
  provider. No raw-file scan, CSV row cap, or lexical/generic answer fallback.
- Sends only the top 1–20 blocks (default 8, at most 2000 characters per block)
  plus up to six previous question/answer pairs, not the entire corpus.
  Follow-up retrieval includes recent user questions to retain the subject.
- Instructs the provider to answer from current evidence, mark missing evidence,
  and cite numbered sources. Each displayed citation includes a source-registry
  link, source ID, block ID and excerpt. Similarity does not guarantee relevance
  or exhaustive coverage; verify important claims against the displayed evidence.
- Keeps up to 20 exchanges **per domain** in `domain_chat_history`. Clearing one
  domain leaves the others intact. The form pins its domain so another browser
  tab's domain selection does not change a submitted question's scope.

## Availability and limits

GET only reads configuration, session history and local index counts: it neither
discovers provider models nor calls chat/embedding providers or the automatic
node heartbeat. The page displays current embedded/total non-heading block
counts. No usable vectors produces a clear error without contacting the LLM;
embedding errors, provider failures and empty answers are surfaced instead of
saved as successful exchanges. No relevant retrieved evidence yields an explicit
no-sources response without an LLM request.

Only **imported, currently embedded records** are searchable. Files that have not
been imported, missing/outdated/wrong-model vectors, and separately stored
artifacts not represented by embedded records are outside retrieval. Contributions
do not supply vectors automatically. Partial coverage is shown on the page.
Use the existing resumable indexing workflow, for example:

```bash
python manage.py embed_blocks --domain <domain> --status
python manage.py embed_blocks --domain <domain>
```

The second command creates embeddings; opening Chat does not create any. The
legacy aggregate `default` registry is narrowed for Chat to default-owned sources,
never treated as permission to search other domains.

## Compatibility and existing free-chat data

`jira-support-chat` and `ollama-chat` URL names remain valid. GET redirects to
`support-chat`, preserving domain, notices and optional source filters. Jira
POSTs use the canonical grounded path.

Old Ollama/free-chat POST actions (`ask`, `save`, `save_import`,
`save_import_semantic`, `save_entry`, `import_entry`, `semantic_entry`, `clear`)
remain compatibility endpoints; they are not another submenu chat. Existing
saved Markdown and `ollama_chat_history` are not deleted or automatically
imported. Save/import actions on an existing entry still work via its original
session index. Their success notices redirect into the canonical page.
New free-chat entries are domain-tagged; only matching tagged history is used
for free-chat continuity or rendered after a POST error. Old unscoped support
and free-chat history is deliberately **not migrated** into Domain Chat: its
domain ownership cannot be established safely. Such history remains stored,
and legacy untagged entries can still be explicitly saved/imported through the
compatibility POST endpoint; entries tagged to another domain are rejected.

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
