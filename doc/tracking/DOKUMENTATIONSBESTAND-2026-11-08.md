---
project: ki-knowledge
agent_project: ki-knowledge
scope: tracking
created: null
updated: "2026-11-08 08"
update_reason: "Archivierung des historischen Widget-Konzepts festgehalten"
status: draft
semantic_blocks:
  - method
  - inventory
  - reviewed
  - unstructured-files
  - coherence-findings
  - remaining-work
relations:
  - target: README.md
    type: parent
    reason: "Bestands- und Umsetzungsberichte"
  - target: ../architecture/KI-KNOWLEDGE-KONZEPT.md
    type: reference
    reason: "Neuer fachlicher Gesamtentwurf"
  - target: ../features/archiv/README.md
    type: reference
    reason: "Archivierter älterer Fachbestand"
---

# Dokumentationsbestand, 8. November 2026

<a id="method"></a>
## Vorgehen und Grenzen [method]

Die Dokumentation wird anhand ihrer semantischen Abschnitte fachlich geprüft.
Bestätigte Aussagen, Vorschläge, vorhandene Implementierungen und Legacy werden
getrennt; veraltete Inhalte bleiben im jeweiligen Bereichsarchiv erhalten.
Der neue [Gesamtentwurf](../architecture/KI-KNOWLEDGE-KONZEPT.md) verbindet
bereits geklärte Aussagen, ohne ältere Implementierungen als fertiggestelltes
neues Wissensmodell auszugeben.

Die folgende Zählung erfasst ausschließlich H2-Überschriften außerhalb von
Codeblöcken und prüft, ob sie eine formal gültige Block-ID am Zeilenende
tragen. Sie prüft **nicht** Inhalt, Aktualität, YAML-Zuordnung oder
Querverweise. Auch bereits getaggte Bereiche müssen fachlich überprüft werden.
Eine Datei ohne H2 erscheint nicht als Datei mit fehlenden IDs.

<a id="inventory"></a>
## Bestandsaufnahme [inventory]

Stand 2026-11-08 01: 90 Markdown-Dateien, 526 H2-Überschriften; 294 H2 in
40 Dateien tragen noch keine Block-ID. Archiv- und Bereichs-READMEs sind
mitgezählt.

| Bereich | Dateien | H2 ohne ID / H2 gesamt | Dateien mit fehlender ID |
|---|---:|---:|---:|
| Dokumentationswurzel | 2 | 0 / 11 | 0 |
| architecture | 13 | 0 / 99 | 0 |
| archive | 14 | 56 / 60 | 11 |
| deployment | 11 | 76 / 79 | 9 |
| features | 17 | 52 / 103 | 5 |
| guides | 11 | 0 / 58 | 0 |
| integration | 5 | 13 / 15 | 2 |
| refactorings | 8 | 61 / 63 | 6 |
| tracking | 9 | 36 / 38 | 7 |

Die Zählung erfolgte unmittelbar vor Anlage dieses Berichts; seine eigenen
vier getaggten Abschnitte sind in der Tabelle nicht enthalten.
Die jüngste Dateiliste und die zusätzlichen Befunde unten stammen von
2026-11-08 03; die Tabelle bleibt eine datierte frühere Momentaufnahme.

**Agentenbearbeitung, 2026-11-08 03:** Eine erneute maschinelle Prüfung
umfasste 92 Markdown-Dateien und 535 H2-Überschriften außerhalb von
Codeblöcken. Davon fehlen bei 274 H2 in 38 Dateien IDs. Alle Verzeichnisse
haben eine README und alle nicht archivierten Unterbereiche einen lokalen
Archivordner. Die READMEs erwähnen alle Markdown-Dateien ihres jeweiligen
Ordners. YAML-Header und Pflichtfelder sind vorhanden; die vorhandenen
Blocklisten stimmen mit den bereits vergebenen H2-IDs überein. Relative
Link- und Relationsziele wurden auf Existenz geprüft, nicht jedoch sämtliche
Fragmente, Gegenseitigkeit oder externe Quellen. Die Prüfung bestätigt weder
Aktualität noch fachliche Richtigkeit.

<a id="reviewed"></a>
## Erste geprüfte Bereiche [reviewed]

- Der [Retrieval-Überblick](../features/knowledge_retrieval.md) trennt
  gewünschte Funktionen und Domain-Chat von
  [archivierten Jira-Beispielen](../features/archiv/RETRIEVAL_JIRA_ALTPFADE.md).
- Die ältere Graph-Explorer-Seite behauptete allgemeine Quellenabdeckung,
  obwohl ihr Skript Jira-Cache und Jira-Graph verwendet. Sie liegt nun im
  [Facharchiv](../features/archiv/knowledge_graph_explorer.md).
- Die [frühere Pipelinezeichnung](../architecture/archiv/FRUEHERE_DATENFLUESSE.md)
  vermischte getrennte Arbeitswege und strukturelle mit semantischer Zerlegung.
- Falsche Empfehlungen, `stackctl normalize` als lesende Validierung oder
  Manifestgenerator zu verwenden, sind im
  [Deploymentarchiv](../deployment/archiv/NORMALIZE_FEHLANNAHMEN.md)
  eingeordnet und aus den aktiven Befehlsbeispielen entfernt.
- Die frühere Annahme eines automatischen Providerwechsels trotz expliziter
  Auswahl ist [archiviert](../deployment/archiv/PROVIDER_DETECTION_ALTKONZEPT.md).
  Die Einordnung wurde anhand des Projektadapters und `ki_core.chat` geprüft;
  weitere Providerbeispiele in den Deploymenttexten bleiben zu prüfen.
- Der [Domain-Chat](../features/support_chat.md) wurde semantisch gegliedert;
  seine Aussagen zum Implementierungsstand wurden dabei nicht vollständig neu
  gegen Code geprüft.
- [Werkstatt-Wireframes](../features/knowledge-workbench-design.md) und
  [historischer Ausgabeentwurf](../features/knowledge_presentation_requirements.md)
  haben nun semantische IDs und Verweise zum fachlichen Konzept. Ihre
  Implementierungs- und Anforderungsaussagen sind damit nicht neu bestätigt.
- Ein ungültiger YAML-Header im
  [archivierten Buchkonzept](../features/archiv/KNOWLEDGE_BLOCKS_BOOK_CONCEPT.md)
  wurde korrigiert, ohne den historischen Inhalt neu zu bewerten.
- Das frühere [Wagtail-inspirierte Widget-Konzept](../refactorings/archiv/widget-building-wagtail-way.md)
  wurde auf Wunsch ins Refactoringarchiv verschoben. Es beschreibt einen
  Vorschlag, nicht den aktuellen Widget-Builder.

<a id="unstructured-files"></a>
## Unstrukturierte Dateien [unstructured-files]

Die folgenden Dateien haben H2-Abschnitte ohne semantische IDs; das ist eine
Strukturlücke, keine pauschale Aussage über ihre fachliche Gültigkeit. Ermittelt
am 2026-11-08 um 03 Uhr anhand von Überschriften außerhalb von Codeblöcken;
die beiden inzwischen gegliederten Entwürfe wurden aus der Liste entfernt.

| Bereich | Dateien |
|---|---|
| Fachfunktionen | [IMPORT_AI_REFINEMENT](../features/IMPORT_AI_REFINEMENT.md), [INFOSITE](../features/INFOSITE.md), [pdf_batch_import](../features/pdf_batch_import.md) |
| Deployment | [CONFIG_MERGE_REFERENCE](../deployment/CONFIG_MERGE_REFERENCE.md), [OLLAMA_REQUIREMENTS](../deployment/OLLAMA_REQUIREMENTS.md), [README](../deployment/README.md), [REFERENCE_FOR_KICLI_ASSIST](../deployment/REFERENCE_FOR_KICLI_ASSIST.md), [STAGES](../deployment/STAGES.md), [TESTING](../deployment/TESTING.md), [UBERSPACE7_IMPLEMENTATION](../deployment/UBERSPACE7_IMPLEMENTATION.md), [UBERSPACE7_REMOTE_DIAGNOSIS](../deployment/UBERSPACE7_REMOTE_DIAGNOSIS.md), [UBERSPACE8_IMPLEMENTATION](../deployment/UBERSPACE8_IMPLEMENTATION.md) |
| Integration | [NEXTCLOUD](../integration/NEXTCLOUD.md), [widgetkit-django-host-integration](../integration/widgetkit-django-host-integration.md) |
| Refactorings | [dashboard_builder_plan](../refactorings/dashboard_builder_plan.md), [distributed-collaboration-plan](../refactorings/distributed-collaboration-plan.md), [navigation-ia-proposal](../refactorings/archiv/navigation-ia-proposal.md), [views-module-architecture](../refactorings/views-module-architecture.md), [widget-building-wagtail-way](../refactorings/archiv/widget-building-wagtail-way.md), [widget-migration-and-admin-plan](../refactorings/widget-migration-and-admin-plan.md) |
| Tracking | [epub-import](epub-import-2026-10-29.md), [live-settings](live-settings-2026-10-29.md), [project-inventory](project-inventory-2026-10-28.md), [project-inventory-followup](project-inventory-followup-2026-10-29.md), [source-access-consolidation](source-access-consolidation-2026-10-29.md), [widget-catalog-preview-audit](widget-catalog-preview-audit.md), [workbench-e4](workbench-e4-2026-10-29.md) |
| Zentrales Archiv | [SYSTEM_OVERVIEW_LEGACY](../archive/SYSTEM_OVERVIEW_LEGACY.md), [features-and-refactor-overview](../archive/developer/features-and-refactor-overview.md), [services-refactor-plan](../archive/developer/services-refactor-plan.md), [infosite_html_output_report](../archive/infosite_html_output_report.md), [jira_daily_timeline](../archive/jira-naming/jira_daily_timeline.md), [jira_graph_explorer](../archive/jira-naming/jira_graph_explorer.md), [jira_hybrid_search](../archive/jira-naming/jira_hybrid_search.md), [jira_support_chat](../archive/jira-naming/jira_support_chat.md), [wagtail_cms_integration_report](../archive/wagtail_cms_integration_report.md), [widgetkit-django-extraction](../archive/widgetkit-django-extraction.md), [widgetkit-django-packaging-roadmap](../archive/widgetkit-django-packaging-roadmap.md) |

[requirements-clients.md](../features/requirements-clients.md) ist zusätzlich
inhaltlich unstrukturiert: Es enthält nur H3/H4-Notizen und erscheint daher
nicht in der H2-Zählung. Umgekehrt bedeutet eine vorhandene ID nicht, dass der
betreffende Abschnitt fachlich geprüft wurde.

<a id="coherence-findings"></a>
## Abweichungen vom Gesamtbild [coherence-findings]

| Stelle | Einordnung |
|---|---|
| [Frühere Output-Anforderungen](../features/knowledge_presentation_requirements.md) | Historischer Entwurf; der damalige Ausschluss von Wissensblöcken ist keine aktuelle Produktgrenze. Andere Anforderungen bleiben einzeln prüfbar. |
| [Import und KI-Refinement](../features/IMPORT_AI_REFINEMENT.md) | Der alte Importablauf vermischt Statusübergabe und Inhaltsaufnahme; der ältere Refinement-Schreibweg ist nicht die Werkstatt-Vorschlagsannahme. An den betroffenen Abschnitten markiert. |
| [Werkstattmodell](../architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md) und [Wireframes](../features/knowledge-workbench-design.md) | Werkstattmarkierungen und deren Relationstypen sind nicht automatisch fachliche Wissensblöcke oder deren endgültiges Modell. An Modell, Relationen und Wireframes markiert. |
| [Systemüberblick](../architecture/SYSTEM_OVERVIEW.md#feature-taxonomy) und [Knowledge-Blocks-Bestand](../features/knowledge_blocks.md) | Extrahierte Records und strukturelle Zerlegung sind nicht selbst semantisches Verständnis oder das neue Wissensmodell. Markiert; die übrigen Statusaussagen benötigen weitere Prüfung. |
| [InfoSite](../features/INFOSITE.md) und [PDF-Import](../features/pdf_batch_import.md) | Gemischter Bestand und ungeprüfte ältere Abschnitte sind kenntlich; die Funktionen selbst werden nicht pauschal verworfen. |

<a id="remaining-work"></a>
## Noch zu prüfen [remaining-work]

1. Fachabschnitte mit fehlenden IDs und solche mit vorhandenen IDs einzeln
   gegen Produktziel und gegebenenfalls Implementierung prüfen; nicht allein
   aufgrund des Dateistatus entscheiden.
2. Den übrigen historischen Systemüberblick, insbesondere Feature-Taxonomie,
   Discovery und InfoSite, von nachgewiesenem Bestand und Zielbild trennen.
3. Deployment- und Konfigurationsdokumente weiter prüfen: Die Entfernung der
   falschen `normalize`-Beispiele bestätigt die übrigen Befehle ausdrücklich
   nicht. Allgemeine Betriebsregeln gehören in ihre führende gemeinsame Quelle.
4. Bereichsarchive, semantische IDs, YAML-Relationen und Verweise bei jeder
   weiteren Extraktion aktualisieren; ältere Fragmentlinks nach Möglichkeit
   erhalten.
5. Den Gesamtentwurf nach weiteren fachlichen Prüfungen ergänzen und offene
   Entscheidungen nicht stillschweigend als bestätigt ausgeben.
