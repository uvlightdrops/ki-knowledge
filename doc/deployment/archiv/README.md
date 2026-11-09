---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 01"
update_reason: "Frühere normalize- und Provider-Annahmen archiviert"
status: active
semantic_blocks:
  - document-index
relations:
  - target: ../README.md
    type: parent
    reason: "Deploymentübersicht"
  - target: NORMALIZE_FEHLANNAHMEN.md
    type: child
    reason: "Frühere gefährliche Empfehlungen zu normalize"
  - target: PROVIDER_DETECTION_ALTKONZEPT.md
    type: child
    reason: "Überholte Annahmen zur Provider-Auswahl"
---

# Deploymentarchiv

Für überholte projektspezifische Betriebsdokumente. Bereits als fraglich
gekennzeichnete Anleitungen werden vor dem Verschieben einzeln geprüft.

<a id="document-index"></a>
## Dokumente [document-index]

| Datei | Status | Zweck | Semantische Blöcke |
|---|---|---|---|
| [NORMALIZE_FEHLANNAHMEN.md](NORMALIZE_FEHLANNAHMEN.md) | archived | Überholte Empfehlungen zu normalize | mistaken-use, affected-documents |
| [PROVIDER_DETECTION_ALTKONZEPT.md](PROVIDER_DETECTION_ALTKONZEPT.md) | archived | Frühere Annahmen zur Provider-Auswahl | old-assumption, boundary |

[Zum Deployment](../README.md)
