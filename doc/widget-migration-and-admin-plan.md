# Widget-Migration und Admin-Area-Umbau

## Ziel

Die Seiten des produktiven UI werden aus einem konsistenten Widget-Model gerendert. Alte HTML-Abschnitte bleiben nicht als separate, parallel aktive Layouts bestehen, sondern werden als echte Widget-Definitionen in die Kanon-Registry übernommen. Dadurch werden gespeicherte Layouts für Bereichsseiten persistent, korrekt, nach Domain und Area getrennt und im Builder vollständig nachvollziehbar.

## Grundsatz

- Keine erfundenen Widget-IDs mehr
- Jeder Bereich rendert nur Widgets aus der Registry
- Legacy-HTML wird in Widget-Renderer übersetzt und dort als echte Seite/Area-Komponente geführt
- Builder, Bereichsseiten und Navigation nutzen dieselbe Terminologie: Dashboard, Data Sources, Knowledge, Info Output, Admin, Settings
- Persistenz bleibt pro Area und pro Domain; keine globale Layout-Vererbung mehr

## Phase 1: Inventarisierung der existierenden Seiten

### Data Sources

- Overview / Domain table
- Workspace preparation card
- Issue / CSV card
- PDF card
- Markdown card
- OWL card
- Sources list / import overview
- Job links

### Knowledge

- Overview summary
- Semantic monitor
- Quick semantic tasks
- Records summary
- Artifacts summary
- Quick links / tasks and tools

### Info Output

- Output format overview
- Infosite recent list
- Documents list
- Domain overview table

### Admin

- Active domain overview
- Domain management summary
- System status overview
- Key links into settings and domain management

## Phase 2: Canonical widget registry

- `dashboard_registry.py` bleibt der zentrale Ursprung für echte Widget-IDs und Defaults.
- Jede Widget-Definition bekommt:
  - `widget_id`
  - `area`
  - `category`
  - `label`
  - `description`
  - `default_size`
  - `default_w` / `default_h`
- Fallback-Layouts werden je Area definiert.

## Phase 3: Renderer- und Persistenz-Contract

- `views.py` lädt für jede Area das gespeicherte Layout mit `_load_dashboard_widget_ids()`.
- `DashboardDefinition` und `DashboardWidgetPlacement` bleiben der Persistenz-Speicher.
- Beim Rendern einer Area werden die gespeicherten Widget-IDs in HTML umgewandelt; dabei werden die bisherigen, sinnvoll einsetzbaren HTML-Snippets als inhaltliche Basis verwendet.
- Legacy-Duplikate in den Templates werden entfernt, damit die gespeicherte Auswahl sichtbar und nicht zusätzlich durch fixe alte Karten überschrieben wird.

## Phase 4: Bereichsseiten umrüsten

### 4.1 Data Sources

- Widget-Auswahl nach Area `datasources`
- Persistierte Reihenfolge wird im Page-Grid verwendet
- Veraltete fixe Karten werden durch die widget-basierten Cards ersetzt
- Links werden auf die echten logical targets ausgerichtet: Workspace, Sources, PDF jobs, Knowledge jobs

### 4.2 Knowledge

- Widget-Auswahl nach Area `knowledge`
- Inhaltskarten ersetzen die statischen "Overview"- und "Tasks and tools"-Blöcke
- Linkziel und Terminologie folgen dem realen IA-Modell, nicht mehr veralteten Jira/legacy-Begriffen

### 4.3 Info Output

- Widget-Selection nach Area `infooutput`
- Relevante Output-Widgets ersetzen die feste Formats-Liste
- Übersicht und Dokumentdaten bleiben als echte Bereichsressourcen sichtbar

### 4.4 Admin

- Neuer Area `admin`
- Neuer Landingpage `/admin-overview/`
- Builder zeigt Admin als echten Auswahlbereich an
- Hauptnavigation erhält eine Card/Area "Admin"

## Phase 5: Unified page template architecture

Die Bereiche sollen nicht mehr aus einzelnen, händisch ausgebauten HTML-Templates bestehen, sondern alle denselben Rendering-Mechanismus nutzen:

- Eine generische Area-Page-Template nutzt nur noch: Title, active domain, widget list, maybe global page intro text.
- Das eigentliche Seitenlayout entsteht durch einen reinen Loop über `widget_cards`.
- Jede Card wird aus einem Widget-Renderer erzeugt, der den echten Seiteninhalt erstellt.
- Die Auswahl des Widgets erfolgt durch die persistierte `DashboardWidgetPlacement`-Reihenfolge pro Area + Domain.
- Dieses Muster gilt für Dashboard, Data Sources, Knowledge, Info Output, Admin und Settings.

### Konstruktionsprinzip

- `registry` liefert `WidgetSpec` mit ID und Metadaten.
- `render_widget(area, widget_id, context)` liefert den HTML-Block eines Widgets.
- `area_page_template.html` rendert nur `for card in widget_cards` und verteilt die Cards im Grid.
- Jede Seite enthält kein zusätzliches, fixes HTML mehr, das in den Widget-Loop hineingehört.
- Jede bisherige feste "Tabelle oben", "Kard-Überschrift", "Meta-Panel", "Listung" wird als eigenes Widget in den Registry-Stack übernommen.

### Regel

Wenn ein Bereichsinhalt bisher direkt im Template stand, muss er in ein Widget verschoben werden. Nur noch die Rahmenlogik bleibt im generischen Template.

### Beispiel

`data_sources.html` darf keine harte Tabelle "Domains" mehr direkt außerhalb des Widget-Loops enthalten. Diese Tabelle ist ein Widget wie z. B. `datasources.domain.overview.v1`.

Die gleiche Regel gilt für:

- Knowledge: Overview, Tasks and tools, quick links, semantic cards, records summary, artifacts summary
- Output: format cards, domain overview, recent documents
- Admin: domain management, system status, overview

### Warum das wichtig ist

- Single source of truth für UI-Struktur
- Persistierte Layout-Definitionen arbeiten immer gegen dieselbe Template-Schicht
- Builder passt exakt zur sichtbaren Seite, weil beide denselben Widget-Graphen verwenden
- Späteres Hinzufügen/Rausschalten eines Blocks bedeutet nur noch ein Widget in der Registry bzw. in der Auswahl
- Legacy-Html bleibt nicht als unsichtbare parallel aktive Branche stehen

## Phase 6: Navigation / Builder / Menu cleanup

- Builder zeigt nur echte Bereiche an: Dashboard, Data Sources, Knowledge, Info Output, Admin, Settings
- Nav-Submenu für Admin ergänzt
- Builder-Link wird lokal pro Area und global im Menu nicht dupliziert dargestellt
- Terminologie konsolidiert auf: Dashboard / Data Sources / Knowledge / Info Output / Admin / Settings

## Phase 7: Requirements-Abgleich

Die Anforderungen in `doc/requirements-clients.md` werden anhand der tatsächlichen Implementierung überprüft und mit Haken versehen, sobald sie erfüllt sind. Dabei gilt: nur wirklich implementierte und sichtbare Änderungen werden als erledigt markiert.

## Umsetzungskriterien

Erfolg ist erreicht, wenn:

- jede Area ihre gespeicherte Layout-Auswahl korrekt rendert
- keine Legacy-Layouts in den Bereichsseiten aktiv nebeneinander sichtbar sind
- Builder und Navigation dieselbe Terminologie nutzen
- der Admin-Area im Mainmenu vorhanden ist
- die Requirements-Datei den realen Status widerspiegelt
