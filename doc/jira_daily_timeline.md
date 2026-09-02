# jira_daily_timeline.py

## Zweck

Erstellt eine tägliche Zeitleiste aus Jira-CSV-Daten und verdichtet pro Tag die wichtigsten Themen.

## Was es kann

- CSV importieren
- Issues in den SQLite-Cache schreiben
- Tagesweise Zusammenfassungen bilden
- Issue-Keys und erkannte Themen ausgeben

## Eingaben

- `JIRA_CSV_PATH`
- `JIRA_CSV_ENCODING`
- `JIRA_CSV_DELIMITER`
- `JIRA_CACHE_DB`
- `JIRA_TIMELINE_DAYS`

## Ausgabe

- Pro Tag:
  - Issue-Anzahl
  - erkannte Themen
  - betroffene Issue-Keys

## Wann verwenden

Wenn du sehen willst, was sich über die Zeit in einem Team oder Themenbereich entwickelt hat.

