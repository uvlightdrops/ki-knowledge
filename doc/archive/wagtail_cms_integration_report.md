# Wagtail CMS-Umbau und Entitäten-Integration

## Ziel

Die vorhandene Wissens- und Output-Pipeline sollte als primäre Datengrundlage bestehen bleiben, aber ausgewählte Entitäten sollten zusätzlich als Wagtail-Editierobjekte nutzbar werden. Das betrifft vor allem:

- `SourceDocument`: Entdeckte, importierte und redaktionell bewertete Quellen
- `GeneratedDocument`: automatisch erzeugte Ausgabe-Dokumente
- Wagtail-Katalogseiten, die über bestehende Projekt-/Dokumentdaten hinweg editorial zusammenfassen

Ziel war dabei kein zweites Datenmodell, sondern eine echte CMS-Ebene auf der vorhandenen Canonical-Data-Layer.

## Umsetzung

### 1. Wagtail-Such- und Filterfähigkeit auf CMS-Entitäten

`SourceDocument` und `GeneratedDocument` wurden als `index.Indexed`-Modelle ergänzt. Dadurch können sie in Wagtail-Snippet-Listen nach den wichtigsten Feldern gesucht und nach editorialen Kriterien gefiltert werden.

Beispiele:

- `title`, `file_path`, `editor_notes` werden als Suchfelder genutzt
- `project_id`, `file_type`, `import_status`, `review_status`, `ai_refinement_mode` sind Filterfelder
- Damit lassen sich Snippets in Wagtail ohne zusätzliche kopierte Datenmodelle sauber durchsuchen

### 2. Gemeinsame Wagtail-ViewSet-Abstraktion

In `ki_knowledge/wagtail_cms/wagtail_hooks.py` gibt es jetzt eine gemeinsame Basisklasse `EditorialSnippetViewSet`, die allgemeine Einstellungen bündelt:

- `list_per_page`
- `inspect_view_enabled`
- gemeinsame CMS-Standards für die Snippet-Listen

Damit entfällt Redundanz zwischen Source- und Generated-Document-Listen, ohne die konkrete UI je nach Entität zu verlieren.

### 3. Workflow-/Review-Status als gemeinsamer Helper

Die Statuslogik für Wagtail-Workflow wurde in `EditorialWorkflowMixin` zentralisiert.

Damit wird die gleiche Logik für:

- SourceDocument
- GeneratedDocument
- optional weitere editorialen Modelle

im gleichen Muster verwendet. Das reduziert Code-Duplikate und macht das Verhalten konsistenter.

### 4. Django-Admin-Statusbadges mit gemeinsamem Rendering

In `ki_knowledge/django_site/infosite_admin.py` wurde ein gemeinsamer Badge-Helfer ergänzt. Dadurch werden Statusanzeigen nicht mehrfach manuell als HTML-String konstruiert, sondern aus einer einheitlichen Abstraktion heraus gerendert.

Das betrifft insbesondere:

- Sync-Status von `InfoSiteProject`
- Import-Status von `SourceDocument`

## Architektur-Entscheidung

Die Integration folgt dem bisher gültigen Muster:

- Kernmodelle bleiben die Source of Truth
- Wagtail übernimmt Editorial Experience, Suche, Filter, Workflow und CMS-Ansicht
- keine Datenkopie in separaten CMS-Entitäten

Das ist entscheidend, weil die echten Datenquellen weiterhin in der eigentlichen Wissens- und Import-Pipeline liegen. Wagtail ist hier bewusst ein parallel laufender editorialer Kontext, kein Ersatz.

## Abstraktionen und Bereinigung

Im Rahmen des Umbaues wurden bewusst drei Typen von Wiederholungen reduziert:

1. Gemeinsame Workflow-Status-Logik
2. Gemeinsame Snippet-ViewSet-Defaults
3. Wiederverwendbare Admin-Badge-Logik

Damit bleiben die konkreten Entitäten weiterhin klar und lesbar, aber die allgemeinen Wagtail-/CMS-Mechaniken werden nicht mehrfach neu implementiert.

## Verbleibende Hinweise

- Die CMS-Entitäten sind nun für Seiten-/Snippet-Workflows sauber vorbereitet
- Die echte Wagtail-Seitenstruktur (`wagtail_cms/models.py`) bleibt weiterhin ein ergänzender Katalog-/Editorial-Layer
- Die eigentliche KI-/Source-/Knowledge-Logik wird noch an den Punkten weiter in konkrete CMS-Features hineinwachsen, wenn mehr Inhaltsarten in der editorialen Oberfläche auftauchen

## Fazit

Der Umbau ist jetzt an der richtigen Stelle: Wagtail ist nicht mehr nur als separate Seiten-Landschaft eingebaut, sondern als echtes CMS-Overlay auf ausgewählten, bereits vorhandenen Entitäten. Das erweitert die editorielle Nutzung ohne die Systemgrenzen der eigentlichen Datenpipeline zu verwässern.
