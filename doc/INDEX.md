---
project: ki-knowledge
agent_project: ki-knowledge
scope: documentation
created: "2026-10-29 09"
updated: "2026-11-08 08"
update_reason: "Archivpfad des historischen Widget-Konzepts aktualisiert"
status: active
semantic_blocks:
  - operations
  - architecture
  - features
  - integrations
  - refactorings
  - tracking
  - history
  - shared-sources
---

# Dokumentindex

[Einstieg und Pflegekonventionen](README.md) ·
[Bestandsaufnahme 2026-10-28](tracking/project-inventory-2026-10-28.md)

<a id="betrieb-und-entwicklung"></a>
<a id="operations"></a>
## Betrieb und Entwicklung [operations]

- [Deployment-Infrastruktur](deployment/README.md) — Übersicht der 4 Stages (dev-lokal, dev-mk, prod-k8s, prod).
  - [Ollama: Server-Anforderungen](deployment/OLLAMA_REQUIREMENTS.md) — Hardwareprofile für den separaten Root-Server und Leistungsziele.
  - [Uberspace 7: Umsetzung und Installation](deployment/UBERSPACE7_IMPLEMENTATION.md) — supervisord, Bootstrap und Git-Updates; Hostabnahme offen.
  - [Uberspace 8: Umsetzung und Installation](deployment/UBERSPACE8_IMPLEMENTATION.md) — Bootstrap, systemd-User-Services und Git-Updates; pgvector und Hostabnahme pruefen.
  - [Config Merge Reference](deployment/CONFIG_MERGE_REFERENCE.md) — Konfigurationsschichten und Merge-Semantik.
  - [Stage Details](deployment/STAGES.md) — Detaillierte Anleitung für jede Stage.
  - [Testing](deployment/TESTING.md) — Config-Validierung und Deployment-Tests.
- [Django und Stack](guides/DJANGO_DEV.md).
- [YAML-Konfiguration](guides/YAML_CONFIG_SYSADMIN.md).
- [Live-Konfiguration: Bedienung, Vererbung und Aktivierungsgrenzen](guides/live-settings.md).
- [CLI-Referenz](guides/CLI.md).
- [Paket-Build und kanonischer Quellbaum](guides/packaging.md).
- [CLI oder Weboberflaeche](guides/CLI_VS_DJANGO.md).
- [Frontend-Assets](guides/frontend-assets.md).
- [Textwerkstatt: Bedienung, Build und Betrieb](guides/text-workbench.md).
- [EPUB-Bücher als Markdown-Quellen importieren](guides/epub-import.md).

<a id="architektur-und-modelle"></a>
<a id="architecture"></a>
## Architektur und Modelle [architecture]

- [Django, Wagtail und Widgetkit](architecture/DJANGO-WAGTAIL-WIDGETKIT.md) — technischer Ist-Überblick und Integrationsgrenzen.
- [Ki-Knowledge: fachliches Konzept](architecture/KI-KNOWLEDGE-KONZEPT.md) — Gesamtentwurf.
- [Text- und Wissensblöcke](architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md) — Begriffe, Beispiele und offene Vorschläge.
- [Systemueberblick](architecture/SYSTEM_OVERVIEW.md) — aelterer Architekturstand;
  fuer den aktuellen Befund die datierte Bestandsaufnahme verwenden.
- [Quellen-, Workspace- und Workflow-Konzept](architecture/SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md).
- [InfoSite-Architektur](architecture/INFOSITE_ARCHITECTURE.md).
- [Content-Modell: Einfuehrung](architecture/CONTENT-MODEL-MATRIX-INTRO.md).
- [Content-Modell: Matrix](architecture/CONTENT-MODEL-MATRIX.md).
- [Content-Modell: historische Dokumentauswertung](architecture/CONTENT-MODEL-MATRIX-FROM-DOCS.md).
- [Dashboard-Seitenlayout](architecture/DASHBOARD-PAGE-LAYOUT-CONCEPT.md).
- [Textwerkstatt: Editor, Wissensblöcke und KI-Gespräch](architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md)
  — Zielbild; erste Umsetzung E0–E4 siehe Betriebsanleitung.

<a id="fachfunktionen-und-anforderungen"></a>
<a id="features"></a>
## Fachfunktionen und Anforderungen [features]

- [Knowledge Blocks](features/knowledge_blocks.md).
- [Retrieval und Analyse](features/knowledge_retrieval.md) — gewünschte Funktion; bestehende Jira-Pfade sind Legacy.
- [Hybride Suche](features/archiv/hybrid_search.md) — Jira-Pfad Legacy, Suche bleibt gewünscht.
- [Graph Explorer](features/archiv/graph_explorer.md) — Jira-Legacy.
- [Knowledge Graph Explorer](features/archiv/knowledge_graph_explorer.md) — Jira-Legacy; frühere allgemeine Quellenbehauptung widerlegt.
- [Support-Chat](features/support_chat.md).
- [Daily Timeline](features/archiv/daily_timeline.md) — Jira-Legacy.
- [PDF-Batch-Import](features/pdf_batch_import.md).
- [Import und KI-Refinement](features/IMPORT_AI_REFINEMENT.md).
- [InfoSite](features/INFOSITE.md).
- [Anforderungen an Wissenspraesentation](features/knowledge_presentation_requirements.md).
- [Client-Anforderungen](features/requirements-clients.md).
- [Textwerkstatt: Markdown-Wireframes und Bedienabläufe](features/knowledge-workbench-design.md)
  — Editor-Entwurf, keine laufende Anwendung.

<a id="integrationen"></a>
<a id="integrations"></a>
## Integrationen [integrations]

- [Nextcloud](integration/NEXTCLOUD.md).
- [Lokale Identitaet und Sync](integration/local-identity-sync.md).
- [widgetkit-django: Host-Integration](integration/widgetkit-django-host-integration.md).

<a id="umbauten-und-offene-konzepte"></a>
<a id="refactorings"></a>
## Umbauten und offene Konzepte [refactorings]

- [Views-Modulaufteilung](refactorings/views-module-architecture.md).
- [Dashboard-Builder-Plan](refactorings/dashboard_builder_plan.md).
- [Verteilte Zusammenarbeit](refactorings/distributed-collaboration-plan.md).
- [Navigation und Informationsarchitektur](refactorings/archiv/navigation-ia-proposal.md) — historischer Vorschlag.
- [Widget-/Admin-Migration](refactorings/widget-migration-and-admin-plan.md).
- [Widgets und Wagtail](refactorings/archiv/widget-building-wagtail-way.md) — historisches Konzept.

<a id="bestands--und-abdeckungsberichte"></a>
<a id="tracking"></a>
## Bestands- und Abdeckungsberichte [tracking]

- [Live-Konfiguration und Providerprüfung, 29.10.2026](tracking/live-settings-2026-10-29.md).
- [Projektbestand und Bereinigungsreihenfolge](tracking/project-inventory-2026-10-28.md).
- [Kurzinventur nach den Umbauten: Beherrschbarkeit, 29.10.2026](tracking/project-inventory-followup-2026-10-29.md).
- [Textwerkstatt E4: kontrollierte KI-Überarbeitung, 29.10.2026](tracking/workbench-e4-2026-10-29.md).
- [EPUB: Umsetzung und erster Buchimport, 29.10.2026](tracking/epub-import-2026-10-29.md).
- [Quellenzugriff konsolidiert: Data Sources und Textwerkstatt, 29.10.2026](tracking/source-access-consolidation-2026-10-29.md).
- [Widget-Katalog: Preview-Audit](tracking/widget-catalog-preview-audit.md) —
  wird auch von einem Abdeckungstest gelesen.

<a id="historisches-material"></a>
<a id="history"></a>
## Historisches Material [history]

Diese Dokumente bewahren Entscheidungen und Verlauf. Sie sind keine aktuellen
Installations- oder Fertigstellungsnachweise.

- [InfoSite-HTML-Ausgabebericht](archive/infosite_html_output_report.md).
- [Wagtail-Integrationsbericht](archive/wagtail_cms_integration_report.md).
- [widgetkit-Extraktionsverlauf](archive/widgetkit-django-extraction.md).
- [Fruehere widgetkit-Packaging-Roadmap](archive/widgetkit-django-packaging-roadmap.md).
- [Frueheres Feature-Inventar](archive/developer/features-and-refactor-overview.md).
- [Frueherer Services-Refactor-Plan](archive/developer/services-refactor-plan.md).
- Alte Jira-Bezeichnungen:
  [Timeline](archive/jira-naming/jira_daily_timeline.md),
  [Graph](archive/jira-naming/jira_graph_explorer.md),
  [Suche](archive/jira-naming/jira_hybrid_search.md),
  [Chat](archive/jira-naming/jira_support_chat.md).

<a id="gemeinsame-quellen-ausserhalb-dieses-repos"></a>
<a id="shared-sources"></a>
## Gemeinsame Quellen ausserhalb dieses Repos [shared-sources]

- [Dokumentationsorganisation](../../../dev_doc/documentation-guidelines/DOCUMENTATION_ORGANIZATION_GUIDE.md).
- [KI-Ökosystem: gemeinsame Workbench-Architektur](../../../dev_doc/architecture/ki-ecosystem-workbench.md)
  — projektübergreifender Entwurf.
- [Server-Management](../../../dev_doc/server-mngm/SERVER_MANAGEMENT_README.md).
- [Historische CLI-Architekturentwuerfe](../../../dev_doc/cli-management/README.md)
  — aus dem bisherigen `docs/` ausgelagert, nicht als aktuelle Roadmap uebernommen.
- [YAML-Betrieb](../../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md).
