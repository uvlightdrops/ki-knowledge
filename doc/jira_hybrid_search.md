# jira_hybrid_search.py

## Zweck

Führt mehrere Suchanfragen gegen den Jira-Cache aus und kombiniert lexikalische und semantische Suche.

## Was es kann

- mehrere Queries pro Lauf
- Keyword-Ranking über Cache
- Embedding-basierte Semantik
- Ollama-Embeddings mit Fallback auf lokale TF-IDF-Vektoren
- Score-Ausgabe für Vergleich und Tuning

## Eingaben

- `JIRA_CSV_PATH`
- `JIRA_CACHE_DB`
- `JIRA_EMBED_MODEL`
- `OLLAMA_BASE_URL`
- `JIRA_CACHE_REFRESH`

## Ausgabe

- Treffer pro Query mit:
  - Combined Score
  - lexical score
  - semantic score

## Wann verwenden

Wenn du suchst wie ein Mensch denkt: nicht nur per Wort, sondern auch per Bedeutung.

