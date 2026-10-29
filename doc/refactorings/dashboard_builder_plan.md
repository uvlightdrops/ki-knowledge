# Dashboard-Builder-Plan für die Django-WebUI

## Zielbild

Die bestehende Django-/Wagtail-WebUI soll von fest verdrahteten Landingpages zu einem konfigurierbaren Dashboard-Builder umgebaut werden. Die Bereiche Data Sources, Internal Knowledge, Info Output und Settings sollen als zusammengesetzte Dashboards aus registrierten Widgets rendern.

Ziel:
- stabile Widget-Identifier
- hierarchische Auswahl aus verfügbaren Widgets
- einfache Platzierung per Layout-Algorithmus
- persistente Speicherung pro User/Domain/Bereich
- serverseitiges Rendering mit Django-Templates, ergänzt durch HTMX (und optional Alpine.js/SortableJS)

## Richtungsentscheidung

- Hauptstack bleibt Django + Templates
- HTMX für Add/Remove/Save/Reorder/Refresh
- Alpine.js nur für kleine Client-State-Themen
- SortableJS nur später, falls echtes Drag-and-Drop benötigt wird
- CSS Grid als Layout-Prinzip
- Server bleibt Source of Truth; Browser-LocalStorage nur als Übergang

## 1. Widget-Identifier-Schema

Empfohlene Struktur:

`{area}.{group}.{name}.v1`

Beispiele:
- `dashboard.domain.management.v1`
- `dashboard.semantic.monitor.v1`
- `data-sources.pdf.import.v1`
- `data-sources.jira.summary.v1`
- `internal-knowledge.records.summary.v1`
- `info-output.documents.recent.v1`
- `settings.layout.registry.v1`

Regeln:
- stabil, eindeutig, versioniert
- nicht aus Überschriften oder Dateinamen ableiten
- Version nur bei inkompatibler Änderung erhöhen

## 2. Widget-Registry

Neues Modul:
- `ki_knowledge/django_site/dashboard_registry.py`

Ein Widget-Eintrag enthält:
- `widget_id`
- `label`
- `area_key`
- `category_path`
- `description`
- `template_name`
- `context_provider`
- `default_size`
- `default_w`
- `default_h`
- `domain_aware`
- `supports_user_config`
- `permission_codename` (optional)
- `feature_flag` (optional)
- `legacy_source` (optional)

Hierarchische Darstellung im Builder:
- Dashboard
  - Domain
  - Knowledge Base
  - Semantic
- Data Sources
  - Markdown
  - PDF
  - Jira
  - OWL
- Internal Knowledge
  - Records
  - Artifacts
  - Semantic
- Info Output
  - Infosite
  - Generated docs
- Settings
  - Layout
  - Config

## 3. Datenmodell

Neues Modul:
- `ki_knowledge/django_site/models_dashboard.py`

### DashboardDefinition
Felder:
- `slug`
- `title`
- `area_key`
- `domain`
- `owner`
- `visibility`
- `is_active`
- `is_system_default`
- `created_at`
- `updated_at`

### DashboardWidgetPlacement
Felder:
- `dashboard`
- `widget_id`
- `container_id` oder `area_path`
- `x`
- `y`
- `w`
- `h`
- `sort_index`
- `config_json`
- `title_override`
- `is_hidden`

Optional später:
- `DashboardPreset`
- `WidgetUserState`

### Persistenz-Scope
Empfohlene Reihenfolge der Auflösung:
1. User + Domain + Bereich
2. Shared Domain Default + Bereich
3. Globaler Bereichsdefault
4. Legacy-Fallback

Damit bleibt die Logik konsistent mit der vorhandenen Domain-Ausrichtung in der Django-UI.

## 4. Neue Module

Empfohlene neue Dateien:
- `ki_knowledge/django_site/dashboard_registry.py`
- `ki_knowledge/django_site/dashboard_services.py`
- `ki_knowledge/django_site/dashboard_views.py`
- `ki_knowledge/django_site/dashboard_layout.py`
- `ki_knowledge/django_site/dashboard_permissions.py`
- `ki_knowledge/django_site/dashboard_context.py`

Neue Templates:
- `ki_knowledge/django_site/templates/kicli_django/dashboard_builder.html`
- `ki_knowledge/django_site/templates/kicli_django/partials/dashboard_canvas.html`
- `ki_knowledge/django_site/templates/kicli_django/partials/widget_frame.html`
- `ki_knowledge/django_site/templates/kicli_django/widgets/...`

Neues Styling:
- `ki_knowledge/django_site/static/kicli_django/css/dashboard-builder.css`

## 5. Betroffene bestehende Dateien

Direkt betroffen:
- `ki_knowledge/django_site/views.py`
- `ki_knowledge/django_site/urls.py`
- `ki_knowledge/django_site/context_processors.py`
- `ki_knowledge/django_site/services.py`
- `ki_knowledge/django_site/templates/base.html`
- `ki_knowledge/django_site/templates/kicli_django/dashboard.html`
- `ki_knowledge/django_site/templates/kicli_django/data_sources.html`
- `ki_knowledge/django_site/templates/kicli_django/knowledge_landing.html`
- `ki_knowledge/django_site/templates/kicli_django/output_landing.html`
- `ki_knowledge/django_site/templates/kicli_django/settings_layout.html`

Diese Dateien sind die Kernstellen der aktuellen UI-Logik und werden als erste Kandidaten für Widget-Auslagerung verwendet.

## 6. Startinventar der vorhandenen Widgets

Zentrale Ausgangsbasis sind die bestehenden `data-layout-box`-Blöcke im Dashboard.

### Aus `dashboard.html`
- `dashboard.domain.management.v1`
- `dashboard.knowledge.summary.v1`
- `dashboard.semantic.quick-tasks.v1`
- `dashboard.semantic.monitor.v1`
- `dashboard.jobs.recent.v1`
- `dashboard.kb.management.v1`
- `dashboard.system.status.v1`
- `dashboard.import.quick.v1`

### Aus `data_sources.html`
- `data-sources.domains.overview.v1`
- `data-sources.files.discovered.v1`
- `data-sources.markdown.summary.v1`
- `data-sources.pdf.summary.v1`
- `data-sources.jira.summary.v1`
- `data-sources.owl.summary.v1`

### Aus `knowledge_landing.html`
- `internal-knowledge.overview.counts.v1`
- `internal-knowledge.fast-access.links.v1`
- `internal-knowledge.tools.catalog.v1`

### Aus `output_landing.html`
- `info-output.formats.catalog.v1`
- `info-output.domains.generated-summary.v1`
- `info-output.documents.recent.v1`

### Aus `settings_layout.html`
- `settings.layout.registry.v1`

## 7. Provider-Schicht

Bestehende Logik aus `ki_knowledge/django_site/services.py` soll nicht direkt in Template- oder Builder-Views landen, sondern in Widget-Provider gekapselt werden.

Ein Provider hat typischerweise:
- `request`
- `domain`
- `widget_config`
- optional `user`

Ein Provider liefert für das Widget:
- Kontextdaten
- Statuswerte
- Listen/Statistiken
- Render-Optionen

Vorteil:
- testbar
- wiederverwendbar
- unabhängig von einer konkreten Landingpage

## 8. Layout-Algorithmus

### Startpunkt
12-Spalten-Grid.

Größenmapping:
- `compact` = 3
- `balanced` = 6
- `wide` = 9
- `full` = 12

### Platzierungslogik
- Reihenfolge: oben nach unten, links nach rechts
- erste freie Position mit ausreichender Breite finden
- Positionen aus `x`, `y`, `w`, `h` in der DB speichern

### Später
- Reflow bei Remove
- Resize-UI
- Drag-and-Drop mit SortableJS

## 9. UI-Flows

### A. Dashboard anzeigen
1. User öffnet Bereich
2. Resolver sucht Dashboard je User/Domain/Bereich
3. falls fehlt: Seed aus Default oder Legacy
4. Canvas rendert Widgets

### B. Dashboard bearbeiten
1. User klickt auf „Layout bearbeiten“
2. Builder zeigt:
   - Widget-Katalog links
   - Canvas mittig
   - Eigenschaften rechts
3. Widget wird ausgewählt und hinzugefügt
4. HTMX aktualisiert Canvas

### C. Widget hinzufügen
- POST mit `widget_id` und `dashboard_id`
- Validierung gegen Registry
- Platzierung berechnen
- Placement speichern
- Canvas neu rendern

### D. Widget konfigurieren
- Widget-spezifisches Formular
- Speicherung in `config_json`
- Widget rendern mit erweiterter Konfiguration

### E. Reset / Duplicate
- auf Bereichsdefault zurücksetzen
- persönliches Dashboard kopieren
- Domain-Default ableiten

## 10. Migrations- und Kompatibilitätsstrategie

Kein Big Bang.

### Phase 1
- Registry und Datenmodell hinzufügen
- bestehende Seiten bleiben sichtbar unverändert

### Phase 2
- bestehende Dashboard-Abschnitte als Widgets extrahieren
- Landingpage bleibt zunächst optisch fast identisch

### Phase 3
- `settings/layout/` zur echten Builder-UI umbauen

### Phase 4
- Bereichsseiten über Dashboard-Resolver rendern

### Phase 5
- optional weitere Detailseiten widgetisieren

### Fallback-Regeln
- wenn Widget fehlschlägt: Fehlerkarte statt Seitenabsturz
- wenn kein Dashboard existiert: Seed erzeugen
- wenn Feature deaktiviert: Legacy-Template weiter benutzen

## 11. Reihenfolge der Umsetzung in kleinen PRs

### PR 1 — Widget-Inventar + Registry-Skelett
- vorhandene Widgets inventarisieren
- `dashboard_registry.py` anlegen
- ID-Schema festlegen
- interne Debug-Ansicht alternativ

### PR 2 — Persistente Modelle + Migrationen
- `DashboardDefinition`
- `DashboardWidgetPlacement`
- erste Migration
- Resolver-Service

### PR 3 — Widget-Renderer + Provider
- `widget_frame.html`
- erste Provider
- erster widgetbasierter Renderpfad

### PR 4 — Builder Minimalversion
- neue Builder-Route
- hierarchischer Widget-Katalog
- Add/Remove/Resize/Reorder per HTMX
- Speicherung aktiv

### PR 5 — Layout-Algorithmus
- 12-Spalten-System
- Autoplace
- Reflow-Grundlogik

### PR 6 — Dashboard-Bereich migrieren
- Haupt-Dashboard auf Resolver + Renderer

### PR 7 — Data Sources / Internal Knowledge / Info Output
- Bereichsseiten widgetisieren
- Services weiterverwenden

### PR 8 — Shared Defaults + Domain-Layouts
- defaults, reset, duplicate

### PR 9 — UX-Ausbau
- Alpine.js
- optional SortableJS
- Suche, Collapse, Konfigurationsdialoge

### PR 10 — Doku + Restmigration
- Architektur dokumentieren
- Legacy-Reste bereinigen

## 12. Test- und Validierungsstrategie

### Modelltests
- Resolver
- Persistenz
- Sichtbarkeit
- Seed-Erzeugung

### Service-Tests
- Registry konsistent
- Provider liefert validen Context
- Placement-Algorithmus funktioniert

### View-Tests
- HTMX-Endpunkte geben korrekte Partials zurück
- Bereichsseiten laden mit Dashboard
- Nutzer-/Domain-Scope korrekt

### Template-/Smoke-Tests
- alle Widgets referenzieren vorhandene Templates
- Fehler werden isoliert dargestellt
- zentrale Seiten rendern weiterhin

## 13. Risiken / Trade-offs

### 1. Monolithische `views.py`
Risiko: bestehende Logik ist stark an eine View gekoppelt.
Gegenmaßnahme: zuerst Provider extrahieren, keine totale Refaktorierung.

### 2. Widget-Zuschnitt zu grob oder zu fein
Gegenmaßnahme: mit groben Widgets starten und später feiner zerlegen.

### 3. Domain-Handling uneinheitlich
Gegenmaßnahme: Resolver tolerant bauen, Persistenz mit Domain-FK bevorzugen.

### 4. HTMX reicht nicht für alles
Gegenmaßnahme: Phase 1 ohne echtes DnD; später optional Alpine/Sortable.

### 5. ID-Stabilität
Gegenmaßnahme: nur versionierte `widget_id` als Schlüssel verwenden.

## 14. Konkrete Empfehlung für den Start

Der niedrigste Risiken-Pfad ist:
1. bestehende Dashboard-Boxen als Seed für Registry und IDs übernehmen
2. Dashboard-Datenmodell einführen
3. Builder im Settings-Bereich verankern
4. HTMX für Add/Remove/Save/Refresh nutzen
5. erst danach `data-sources`, `internal-knowledge` und `info-output` in die Dashboard-Komposition übernehmen

Das ist die sinnvollste nächste technische Stufe für das bestehende Django-Projekt.
