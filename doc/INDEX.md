# Dokumentindex

[Einstieg und Pflegekonventionen](README.md) ·
[Bestandsaufnahme 2026-10-28](tracking/project-inventory-2026-10-28.md)

## Betrieb und Entwicklung

- [Django und Stack](guides/DJANGO_DEV.md).
- [YAML-Konfiguration](guides/YAML_CONFIG_SYSADMIN.md).
- [CLI-Referenz](guides/CLI.md).
- [Paket-Build und kanonischer Quellbaum](guides/packaging.md).
- [CLI oder Weboberflaeche](guides/CLI_VS_DJANGO.md).
- [Frontend-Assets](guides/frontend-assets.md).
- [Textwerkstatt: Bedienung, Build und Betrieb](guides/text-workbench.md).

## Architektur und Modelle

- [Systemueberblick](architecture/SYSTEM_OVERVIEW.md) — aelterer Architekturstand;
  fuer den aktuellen Befund die datierte Bestandsaufnahme verwenden.
- [Quellen-, Workspace- und Workflow-Konzept](architecture/source-workspace-and-workflow-concept.md).
- [InfoSite-Architektur](architecture/INFOSITE_ARCHITECTURE.md).
- [Content-Modell: Einfuehrung](architecture/content-model-matrix-intro.md).
- [Content-Modell: Matrix](architecture/content-model-matrix.md).
- [Content-Modell: Dokumentauswertung](architecture/content-model-matrix-from-docs.md).
- [Dashboard-Seitenlayout](architecture/dashboard-page-layout-concept.md).
- [Textwerkstatt: Editor, Wissensblöcke und KI-Gespräch](architecture/knowledge-workbench-concept.md)
  — Zielbild; erste Umsetzung E0–E3 siehe Betriebsanleitung.

## Fachfunktionen und Anforderungen

- [Knowledge Blocks](features/knowledge_blocks.md).
- [Retrieval und Analyse](features/knowledge_retrieval.md).
- [Hybride Suche](features/hybrid_search.md).
- [Graph Explorer](features/graph_explorer.md).
- [Knowledge Graph Explorer](features/knowledge_graph_explorer.md).
- [Support-Chat](features/support_chat.md).
- [Daily Timeline](features/daily_timeline.md).
- [PDF-Batch-Import](features/pdf_batch_import.md).
- [Import und KI-Refinement](features/IMPORT_AI_REFINEMENT.md).
- [InfoSite](features/INFOSITE.md).
- [Anforderungen an Wissenspraesentation](features/knowledge_presentation_requirements.md).
- [Client-Anforderungen](features/requirements-clients.md).
- [Textwerkstatt: Markdown-Wireframes und Bedienabläufe](features/knowledge-workbench-design.md)
  — Editor-Entwurf, keine laufende Anwendung.

## Integrationen

- [Nextcloud](integration/NEXTCLOUD.md).
- [Lokale Identitaet und Sync](integration/local-identity-sync.md).
- [widgetkit-django: Host-Integration](integration/widgetkit-django-host-integration.md).

## Umbauten und offene Konzepte

- [Views-Modulaufteilung](refactorings/views-module-architecture.md).
- [Dashboard-Builder-Plan](refactorings/dashboard_builder_plan.md).
- [Verteilte Zusammenarbeit](refactorings/distributed-collaboration-plan.md).
- [Navigation und Informationsarchitektur](refactorings/navigation-ia-proposal.md).
- [Widget-/Admin-Migration](refactorings/widget-migration-and-admin-plan.md).
- [Widgets und Wagtail](refactorings/widget-building-wagtail-way.md).

## Bestands- und Abdeckungsberichte

- [Projektbestand und Bereinigungsreihenfolge](tracking/project-inventory-2026-10-28.md).
- [Quellenzugriff konsolidiert: Data Sources und Textwerkstatt, 29.10.2026](tracking/source-access-consolidation-2026-10-29.md).
- [Widget-Katalog: Preview-Audit](tracking/widget-catalog-preview-audit.md) —
  wird auch von einem Abdeckungstest gelesen.

## Historisches Material

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

## Gemeinsame Quellen ausserhalb dieses Repos

- [Dokumentationsorganisation](../../../dev_doc/DOCUMENTATION_ORGANIZATION_GUIDE.md).
- [KI-Ökosystem: gemeinsame Workbench-Architektur](../../../dev_doc/architecture/ki-ecosystem-workbench.md)
  — projektübergreifender Entwurf.
- [Server-Management](../../../dev_doc/server-mngm/SERVER_MANAGEMENT_README.md).
- [Historische CLI-Architekturentwuerfe](../../../dev_doc/cli-management/README.md)
  — aus dem bisherigen `docs/` ausgelagert, nicht als aktuelle Roadmap uebernommen.
- [YAML-Betrieb](../../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md).
