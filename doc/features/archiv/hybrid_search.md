---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-09 22"
updated: "2026-11-08 00"
update_reason: "Jira-spezifische Suche als Legacy ins Bereichsarchiv verschoben"
status: archived
semantic_blocks:
  - purpose
  - capabilities
  - configuration
  - example
  - use-cases
  - references
relations:
  - target: README.md
    type: parent
    reason: "Bereichsarchiv der Fachfunktionen"
---

# Hybrid Search

> **Legacy:** Der hier beschriebene Jira-spezifische Suchpfad ist veraltet.
> Jira soll künftig ein gleichberechtigtes Eingabe-/Importformat sein; eine
> quellenübergreifende Nachfolge ist damit nicht als umgesetzt behauptet.
> **Suche als Funktion bleibt ausdrücklich gewünscht.**

<a id="purpose"></a>
## Purpose [purpose]

The documented Jira retrieval path combines lexical and semantic search over
the Jira issue cache. This page does not establish support for all sources
registered in the separate KnowledgeStore.

<a id="what-it-does"></a>
<a id="capabilities"></a>
## What it does [capabilities]

- queries multiple natural-language and keyword searches
- combines lexical scoring with semantic similarity
- the example tries Ollama embeddings and falls back to local TF-IDF;
  the Jira retrieval service has its own TF-IDF-based path
- compares results side by side for tuning and debugging

<a id="typical-inputs"></a>
<a id="configuration"></a>
## Typical inputs [configuration]

The example resolves the Jira CSV and cache from application configuration;
it also reads Jira-specific overrides including `JIRA_CACHE_REFRESH` and
`JIRA_EMBED_MODEL`. Shared layers are described in the
[configuration guide](../../guides/YAML_CONFIG_SYSADMIN.md).

<a id="example"></a>
## Example [example]

```bash
python examples/jira_hybrid_search.py "search terms"
```

The example can import Jira issues into the cache and build embeddings. It
does not search arbitrary KnowledgeStore sources.

<a id="best-use-cases"></a>
<a id="use-cases"></a>
## Best use cases [use-cases]

- find conceptually similar records quickly
- compare keyword vs semantic ranking
- build a high-recall first pass before deeper analysis
- inspect keyword and semantic scores for cached issues

<a id="see-also"></a>
<a id="references"></a>
## See also [references]

- [knowledge_retrieval.md](../knowledge_retrieval.md)
- [graph_explorer.md](graph_explorer.md)
- [support_chat.md](../support_chat.md)
- [daily_timeline.md](daily_timeline.md)
