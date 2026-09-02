# jira_support_chat.py

## Zweck

Grounded RAG-Chat über Jira-Daten. Das Tool kombiniert CSV-Cache, Suche, Embeddings und optional den Wissensgraphen.

## Was es kann

- CSV in SQLite-Cache importieren
- Hybrid Retrieval über Keyword + Embeddings
- Fallback auf TF-IDF, wenn Ollama-Embeddings fehlen
- Graph-Erweiterung über verwandte Issues
- Interaktiven Chat mit Quellenanzeige

## Eingaben

- `JIRA_CSV_PATH`
- `JIRA_CACHE_DB`
- `JIRA_GRAPH_DB`
- `JIRA_EMBED_MODEL`
- `JIRA_USE_HYBRID_SEARCH`
- `JIRA_USE_GRAPH`

## Ausgabe

- Antwort des Assistenten
- Quellen-Keys
- optional graph-erweiterte Issue-Keys

## Wann verwenden

Wenn du aus Jira-Daten einen echten Support-Assistenten machen willst, der Antworten begründet und nicht frei halluziniert.

