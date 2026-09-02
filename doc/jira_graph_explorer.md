# jira_graph_explorer.py

## Zweck

Erstellt den Wissensgraphen aus dem Jira-Cache und macht seine Struktur sichtbar.

## Was es kann

- Graph aus Cache neu aufbauen
- Knoten und Kanten zählen
- Nachbarn eines Issues anzeigen
- Cypher-Export für Neo4j oder Lernzwecke schreiben

## Eingaben

- `JIRA_CSV_PATH`
- `JIRA_CACHE_DB`
- `JIRA_GRAPH_CYPHER_PATH`
- `JIRA_GRAPH_ISSUE_KEY`
- CLI-Argument: `issue_key`

## Ausgabe

- Graph-Statistik
- direkte Nachbarn eines Beispiel-Issues
- optional `.cypher`-Datei

## Aufruf

```bash
python examples/jira_graph_explorer.py AE-123
```

Wenn kein Issue übergeben wird, nutzt das Tool `JIRA_GRAPH_ISSUE_KEY` oder sonst das erste Issue aus dem Cache.

## Wann verwenden

Wenn du Beziehungsstrukturen, Clustering oder graphbasierte Erweiterungen nachvollziehen willst.
