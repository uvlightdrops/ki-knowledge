---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-09 07"
update_reason: "Konzept zur Weiterentwicklung ergänzt"
status: active
semantic_blocks:
  - document-index
relations:
  - target: DJANGO-WAGTAIL-WIDGETKIT.md
    type: child
    reason: "Technischer Überblick über die Webanwendung"
  - target: WISSENSWIKI-ZUSAMMENARBEIT.md
    type: child
    reason: "Idee zur gemeinsamen Arbeit an Blöcken und Beziehungen"
  - target: WISSENSWIKI-TECHNIK.md
    type: child
    reason: "Vorläufiger technischer Weg für das Wissenswiki"
  - target: WEITERENTWICKLUNG.md
    type: child
    reason: "Optionen und Empfehlung für die Weiterentwicklung"
---

# Architektur

Konzepte und Modellgrenzen; Statusangaben ersetzen keine aktuelle
Implementierungsprüfung. Jira-spezifische Workflows sind Legacy.

<a id="document-index"></a>
## Dokumente [document-index]

Die Blockspalte zeigt bei längeren Listen einen Auszug.

| Datei | Status | Zweck | Semantische Blöcke |
|---|---|---|---|
| [DJANGO-WAGTAIL-WIDGETKIT.md](DJANGO-WAGTAIL-WIDGETKIT.md) | active | Geprüfte technische Einbindung und Grenzen | scope, django-structure, services-and-data, wagtail-integration, … |
| [WEITERENTWICKLUNG.md](WEITERENTWICKLUNG.md) | draft | Integration, neuer Kern oder Neuentwicklung; Empfehlung und Migrationspfad | starting-point, bridge-findings, options, recommendation, … |
| [KI-KNOWLEDGE-KONZEPT.md](KI-KNOWLEDGE-KONZEPT.md) | draft | Fachlicher Gesamtentwurf und Grenzen des Ist-Stands | purpose, knowledge-core, intake, work-and-review, … |
| [WISSENSWIKI-ZUSAMMENARBEIT.md](WISSENSWIKI-ZUSAMMENARBEIT.md) | draft | Gemeinsames Denken, Blöcke und KI-Vorschläge | starting-point, shared-work, blocks-and-relations, … |
| [WISSENSWIKI-TECHNIK.md](WISSENSWIKI-TECHNIK.md) | draft | Möglicher technischer Weg und offene Entscheidungen | boundary, existing-parts, storage-and-identity, … |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | active | Ausrichtung und historisch gewachsener Systemüberblick | product-direction, system-architecture, feature-taxonomy, data-flow, … |
| [TEXT-AND-KNOWLEDGE-BLOCKS.md](TEXT-AND-KNOWLEDGE-BLOCKS.md) | draft | Wissensblockkonzept und Vorschläge | distinction, relation-proposal, change-proposal, domain-proposal, … |
| [SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md](SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md) | active | Gemeinsames Quelleninventar und Arbeitsabläufe | shared-inventory, related-documentation, purpose, core-idea, … |
| [KNOWLEDGE-WORKBENCH-CONCEPT.md](KNOWLEDGE-WORKBENCH-CONCEPT.md) | draft | Textwerkstatt und weiterführendes Zielbild | recommendation, vision, existing-functionality, application-integration, … |
| [CONTENT-MODEL-MATRIX.md](CONTENT-MODEL-MATRIX.md) | active | Datenmodelle und Speichergrenzen | storage-boundary, infosite-project, source-document, generated-document, … |
| [CONTENT-MODEL-MATRIX-INTRO.md](CONTENT-MODEL-MATRIX-INTRO.md) | draft | Einführung in die Modellmatrix | content-model, matrix-purpose, matrix-dimensions, mirroring-principle, … |
| [CONTENT-MODEL-MATRIX-FROM-DOCS.md](CONTENT-MODEL-MATRIX-FROM-DOCS.md) | archived | Historische Dokumentauswertung | infosite-project, source-document, generated-document, knowledge-blocks, … |
| [DASHBOARD-PAGE-LAYOUT-CONCEPT.md](DASHBOARD-PAGE-LAYOUT-CONCEPT.md) | draft | Dashboard-Layoutkonzept | goal, layout-model, design-rules, builder-workflow, … |
| [INFOSITE_ARCHITECTURE.md](INFOSITE_ARCHITECTURE.md) | archived | Historische InfoSite-Architekturanalyse | current-state, core-concepts, django-architecture, implementation-roadmap, … |

[Bereichsarchiv](archiv/README.md) · [Zur Dokumentation](../README.md)
