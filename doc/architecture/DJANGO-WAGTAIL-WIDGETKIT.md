---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-08 08"
update_reason: "Verweis auf archiviertes Widget-Konzept aktualisiert"
status: active
semantic_blocks:
  - scope
  - django-structure
  - services-and-data
  - wagtail-integration
  - widgetkit-integration
  - limits-and-sources
relations:
  - target: README.md
    type: parent
    reason: "Architekturübersicht"
  - target: CONTENT-MODEL-MATRIX.md
    type: reference
    reason: "Detaillierte Daten- und Speichergrenzen"
  - target: ../integration/widgetkit-django-host-integration.md
    type: reference
    reason: "Bisherige Beschreibung des Widgetkit-Hostvertrags"
  - target: ../refactorings/README.md
    type: reference
    reason: "Herkunft der historischen Umbaupläne und Berichte"
  - target: ../refactorings/archiv/widget-building-wagtail-way.md
    type: reference
    reason: "Historisches Wagtail-inspiriertes Widget-Konzept"
---

# Django, Wagtail und Widgetkit

<a id="scope"></a>
## Einordnung [scope]

Technischer Überblick über die heutige Einbindung der Weboberfläche, nicht
das neue fachliche Wissensmodell. **Agentenbearbeitung 2026-11-08:** Die sechs
Refactoring-Dokumente wurden gelesen und die hier beschriebenen Grenzen
stichprobenartig am aktuellen Quellcode überprüft. Der Überblick ist keine
vollständige Prüfung aller Routen, Berechtigungen oder Widgets. Die
[Content-Modell-Matrix](CONTENT-MODEL-MATRIX.md) ergänzt die Speichergrenzen;
das [fachliche Konzept](KI-KNOWLEDGE-KONZEPT.md) beschreibt das Zielbild.

<a id="django-structure"></a>
## Django-Anwendung [django-structure]

`ki_knowledge.django_site` stellt die Django-Webanwendung mit Templates,
statischen Dateien, ORM-Modellen und Views bereit. Die zentrale
[URL-Konfiguration](../../ki_knowledge/django_site/urls.py) bindet unter
anderem Data Sources, Knowledge mit Textwerkstatt, Info Output, Admin und
Settings ein. Die InfoSite- und Textwerkstatt-Routen haben eigene Includes.
Wagtail wird unter `/cms/`, `/cms-admin/` und `/cms-documents/` eingebunden;
die Hauptanwendung läuft nicht innerhalb des Wagtail-Seitenbaums.

Die frühere große Views-Datei ist als
[Kompatibilitätsfassade](../../ki_knowledge/django_site/views.py) erhalten.
Implementierungen liegen nach Verantwortlichkeiten aufgeteilt, beispielsweise
in `views_dashboard.py`, `views_source_workspace.py`,
`views_source_browser.py`, `views_chat.py`, `views_pdf.py` und
`views_workbench.py`. `views_data_sources.py` und `services.py` erhalten
ältere Importe als Fassaden; sie sind nicht die vorgesehenen neuen
Eigentümermodule. Diese Aufteilung ist keine vollständige Entkopplung von
Django: Auch `django_site` enthält weiterhin fachnahe Services und Adapter,
und bestehende Aufrufer verwenden teils noch Fassaden.

<a id="services-and-data"></a>
## Services und Datenhaltung [services-and-data]

Wiederverwendbare Logik liegt teilweise in `ki_knowledge/services/`, während
`django_site` HTTP, ORM und anwendungsspezifische Integration übernimmt.
Beispielsweise orchestriert `DocumentImportService` die Import-Statusjobs;
`DjangoImportDocuments` aktualisiert die ausgewählten ORM-Dokumente
transaktional. Dieser Weg markiert Status und extrahiert nicht selbst Inhalte.
Andere Import- und PDF-Pipelines besitzen eigene Wege.

Die Django-Datenbank ist standardmäßig SQLite; bei konfigurierter
PostgreSQL-DSN verwendet die Einstellung PostgreSQL. Dateien, der allgemeine
KnowledgeStore und der separate InfoSite-Blockspeicher sind nicht mit der
Django-Datenbank gleichzusetzen. Der Begriff „Knowledge Block“ in bestehenden
Stores bezeichnet noch nicht automatisch den im
[Wissensblockentwurf](TEXT-AND-KNOWLEDGE-BLOCKS.md) beschriebenen fachlichen
Begriff. Jira-spezifische Routen und Services bleiben vorhandener Legacy-Code;
allgemeine Suche, Retrieval und Chat bleiben gewünschte Produktfunktionen.

<a id="wagtail-integration"></a>
## Wagtail als redaktionelle Schicht [wagtail-integration]

Wagtail und `ki_knowledge.wagtail_cms` sind neben der Django-Anwendung
installiert. Wagtail verwaltet eigene Katalogseiten, deren redaktionelle
Einleitungen und Notizen sowie deren Seitenrevisionen und Veröffentlichung.
Die Kataloge zeigen InfoSite-Projekte und vorhandene Projektblöcke; sie
ersetzen nicht die Quellenaufnahme oder die InfoSite-Pipeline.

`SourceDocument` und `GeneratedDocument` sind dieselben Django-Modelle, die
als Wagtail-Snippets registriert werden: Import-/Generierungsstatus und
redaktionelle Prüfung sind getrennte Zustände, keine zwei Dokumentregister.
Die Snippet-Oberfläche kann neben redaktionellen Feldern auch ausgewählte
Registerfelder bearbeiten. Für InfoSite-Blöcke liest `InfoSiteBlockReader`
den vorhandenen Blockspeicher; ein Katalogaufruf erzeugt weder Seiten noch
einen Store. Fehlende Seiten werden ausdrücklich mit
`python manage.py setup_wagtail_cms` angelegt und veröffentlicht; vorhandene
Seiten und ihre Veröffentlichungszustände bleiben dabei erhalten.

Die Projektzuordnung der Detailseiten erfolgt über eine gespeicherte Projekt-ID,
nicht über einen Foreign Key. Nicht jede neue Projektliste hat deshalb
automatisch eine veröffentlichte Detailseite. Näheres zur Eigentümerschaft
und den Statusgrenzen steht in der
[Content-Modell-Matrix](CONTENT-MODEL-MATRIX.md#0-verbindliche-speicher--und-adaptergrenze-p2).

<a id="widgetkit-integration"></a>
## Widgetkit und Dashboard-Builder [widgetkit-integration]

`widgetkit-django` ist ein eigenständiges Schwesterpaket und als Django-App
eingebunden. Es stellt wiederverwendbare Builder- und Katalogbausteine,
Registry- und Layout-Verträge, Templates, Grid- und Vorschauhilfen bereit.
Es liefert außerdem Bausteine für Tabellen und eine Settings-Oberfläche, die
ki-knowledge an ausgewählten Stellen nutzt. Die Projektdetails stehen in
der [widgetkit-django-Dokumentation](../../../widgetkit-django/README.md)
und ihrem [Host-Integrationsvertrag](../../../widgetkit-django/docs/host-integration.md);
die Links setzen das Schwester-Repository im Workspace voraus.

Ki-knowledge bleibt der konkrete Host:

- `dashboard_registry.py` definiert Widget-IDs, Metadaten und Defaults;
  `CallbackWidgetRegistry` verbindet diese mit dem Paket.
- `layout_targets.py` definiert Bereiche und Seitenziele; der Host bestimmt
  aktive Domain, Sessionauswahl, Routen und Daten für die Widgets.
- `DjangoDashboardLayoutStore` verwendet `DashboardDefinition` und
  `DashboardWidgetPlacement`. Layouts sind nach Domain, Bereich,
  Unterseite und optionalem Besitzer unterscheidbar. Beim Laden wird ein
  persönliches Layout vor einem gemeinsamen und danach ein Default verwendet;
  ein explizit leeres gespeichertes Layout ist nicht dasselbe wie ein fehlendes.
  Die Dashboard-Startseite besitzt zusätzlich einen eigenen Rendering-Fallback,
  weshalb daraus kein einheitliches Leerzustandsverhalten aller Seiten folgt.
- Der Builder unter `/settings/layout/builder/` ruft den Paket-Controller mit
  Hostadaptern auf. Er erlaubt, registrierte Widgets auszuwählen und ihre
  Anordnung zu bearbeiten. Die konkreten Bereichsseiten bereiten ihre Karten
  und Inhalte selbst auf; nicht jede Seite oder jeder Builder-Link ist damit
  automatisch vollständig vereinheitlicht.
- Der Widget-Katalog zeigt begrenzte Beispieldaten als lesende Vorschau;
  daneben existiert ein projektspezifischer Widget-Shell-Builder. Diese sind
  von der Live-Datenaufbereitung zu unterscheiden.

Das separate, frameworkneutrale [WidgetKit-Projekt](../../../widgetkit/README.md)
beschreibt Widget-Daten und Rendering. Obwohl `widgetkit` als Abhängigkeit
deklariert ist, nutzen die hier geprüften Renderpfade weiterhin
`ki_knowledge.widgetkit_core` und `ki_knowledge.widgetkit_renderer`. Eine
vollständige Umstellung auf das externe Core-Paket ist daraus nicht abzuleiten.

<a id="limits-and-sources"></a>
## Grenzen und Herkunft [limits-and-sources]

Der [Views-Bericht](../refactorings/views-module-architecture.md) dokumentiert
die Aufteilung und einzelne Extraktionsschritte; die
[Dashboard-](../refactorings/dashboard_builder_plan.md) und
[Widget-Migrationspläne](../refactorings/widget-migration-and-admin-plan.md)
enthalten weiterhin Vorschläge neben inzwischen umgesetzten Teilen.
„Wagtail-artige“ Widgets aus dem
[Konzept](../refactorings/archiv/widget-building-wagtail-way.md) sind nicht
gleichbedeutend mit Wagtail-Snippets oder einem vollständig über Wagtail
verwalteten Builder.

Der Stand beruht insbesondere auf `django_site/settings.py`, `urls.py`,
`views_dashboard.py`, `views_common.py`, `layout_store.py`,
`dashboard_registry.py`, `page_widgets.py`, `widget_catalog_preview.py`,
`wagtail_cms/models.py`, `wagtail_hooks.py` und
`services/infosite_catalog.py`. Prozessberichte, Synchronisation und
Navigation sind damit nicht in allen Einzelheiten neu abgenommen.
