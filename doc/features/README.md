---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: null
updated: "2026-11-08 03"
update_reason: "Semantische Gliederung für Werkstatt- und Ausgabeentwürfe ergänzt"
status: active
semantic_blocks:
  - document-index
relations:
  - target: archiv/README.md
    type: child
    reason: "Archiv der Fachfunktionen"
---

# Fachfunktionen

Funktionen und Entwürfe mit unterschiedlichen Prüfständen. Jira-spezifische
Altpfade sind Legacy; Jira soll künftig ein gleichberechtigtes Eingabe-/
Importformat sein. Knowledge Retrieval, Suche und Chat bleiben gewünschte
Funktionen; der Status eines Dokuments bewertet nicht ihren Produktwert.
`active` bestätigt nicht die fachliche Aktualität.

<a id="document-index"></a>
## Dokumente [document-index]

Die Blockspalte zeigt höchstens vier IDs; „offen“ bedeutet noch nicht getaggt.

| Datei | Status | Zweck | Semantische Blöcke |
|---|---|---|---|
| [knowledge_blocks.md](knowledge_blocks.md) | active | Automatische Blockextraktion und Store | purpose, capabilities, components, usage, … |
| [knowledge_retrieval.md](knowledge_retrieval.md) | draft | Retrieval-Ziel und Legacy-Abgrenzung | feature-index, hybrid-retrieval, graph-analysis, domain-chat, … |
| [support_chat.md](support_chat.md) | active | Domain-Chat und Grenzen | purpose, capabilities, availability, compatibility, … |
| [INFOSITE.md](INFOSITE.md) | active | Import-Control-Vertrag; übrige Aussagen ungeprüft | offen |
| [IMPORT_AI_REFINEMENT.md](IMPORT_AI_REFINEMENT.md) | active | Älterer Import- und Refinement-Ablauf; teilweise überholt | offen |
| [pdf_batch_import.md](pdf_batch_import.md) | active | PDF- und Buch-Pipeline; Arbeitswege einzeln prüfen | offen |
| [knowledge_presentation_requirements.md](knowledge_presentation_requirements.md) | draft | Historische Output-Anforderungen; alter Scope keine Produktgrenze | vision, historical-scope, historical-exclusions, configuration, … |
| [requirements-clients.md](requirements-clients.md) | draft | Unstrukturierte UI-Aufgaben und fachlich offene Fragen | keine H2 |
| [knowledge-workbench-design.md](knowledge-workbench-design.md) | draft | Werkstatt-Wireframes; Markierungen nicht mit Wissensblöcken gleichsetzen | workspace, marking-workflow, ai-conversation, review-changes, … |

[Bereichsarchiv: ältere Fachkonzepte und Jira-Altpfade](archiv/README.md)

[Zur Dokumentation](../README.md)
