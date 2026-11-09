---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 03"
update_reason: "YAML-Header des archivierten Konzepts korrigiert"
status: archived
semantic_blocks:
  - curation-guidelines
relations:
  - target: README.md
    type: parent
    reason: "Archiv der Fachfunktionen"
  - target: ../knowledge_blocks.md
    type: reference
    reason: "Ausgangsdokument der früheren Leitlinien"
---

# Früheres Buch- und Wissensblock-Konzept

**Agentenbearbeitung, 2026-11-08:** Ein unbeabsichtigter Eintrag im YAML-Header
wurde entfernt; der archivierte Inhalt wurde dabei nicht neu bewertet.

Der folgende Ansatz ist Legacy und kein Zielmodell für die neue Planung.
Er wurde aus den [Knowledge Blocks](../knowledge_blocks.md#curation-guidelines)
übernommen; auch die übrigen dort genannten Ideen sind einzeln neu zu bewerten.

<a id="curation-guidelines"></a>
## Frühere Leitlinien für Review und Kuratierung [curation-guidelines]

Hintergrund war eine externe Einschätzung mit dem Titel
„Wissen semantische Blocks workflow“. Diese Datei ist nicht Bestandteil des
Repositorys; der bisherige relative Verweis war nicht auflösbar. Die folgenden
Punkte beschreiben frühere Leitlinien, keinen durchgängig nachgewiesenen Ist-Stand.

- Langfristige Idee: Extraktion (OCR, Segmentierung, LLM) über Jobs ausführen
  und Status und Ergebnis in der UI zeigen. Dies ist keine Aussage über jeden
  aktuellen Importpfad; InfoSite Import Control führt beispielsweise eine
  [synchrone Statusübergabe](../INFOSITE.md#import-control-current-execution-contract) aus.
- Ein Buch hat eine natürliche Hierarchie (Buch → Kapitel → Unterkapitel → Blöcke). Sie wird als eigenes Strukturmodell gespeichert, nicht als Wagtail-Seitenbaum, damit Inhaltsverzeichnisse vergleichbar bleiben.
- Blöcke sind einzelne Datensätze (`KnowledgeBlockRecord`) mit `block_type` (z. B. Definition, Argumentation, Beispiel), Reihenfolge und Herkunft (Seite/Position), keine Wagtail-Seiten und kein StreamField.
- Human-in-the-loop: Redakteure prüfen extrahierte Blöcke, fassen sie zusammen, teilen, verschieben, korrigieren und geben sie frei. Wagtail-Workflow greift auf Buch-/Kapitelebene, pro Block genügt ein Review-Status.
- Embedding-Speicherung und PostgreSQL-Anbindung sind getrennt nach ihrem
  jeweiligen Implementierungsstand zu prüfen; der Satz ist kein
  Migrationsnachweis.
