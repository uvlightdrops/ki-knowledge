---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 01"
update_reason: "Überholte Annahmen zu stackctl normalize aus Betriebsdokumenten ausgelagert"
status: archived
semantic_blocks:
  - mistaken-use
  - affected-documents
relations:
  - target: README.md
    type: parent
    reason: "Deploymentarchiv"
  - target: ../README.md
    type: reference
    reason: "Deploymentübersicht"
---

# Frühere Annahmen zu normalize

<a id="mistaken-use"></a>
## Überholte Verwendung [mistaken-use]

Ältere Deploymenttexte empfahlen `stackctl normalize` fälschlich als
lesenden Konfigurationscheck, zur Ausgabe einer zusammengeführten YAML-Datei
oder sogar zur Generierung von Kubernetes-Manifesten. Ein Beispiel leitete
seine Ausgabe in eine Datei um und empfahl anschließend, diese mit `kubectl`
anzuwenden.

Diese Annahmen sind **nicht gültig**: `normalize` kann Projektdateien ändern
und Git-Commits anlegen. Die Beispiele werden hier bewusst nicht als
ausführbare Befehle wiedergegeben. Für die tatsächliche Bedienung und
Seiteneffekte ist die führende stackctl-Dokumentation maßgeblich.

<a id="affected-documents"></a>
## Herkunft [affected-documents]

Die falschen Empfehlungen standen in der
[Deploymentübersicht](../README.md), den früheren Texten zu
[Konfigurationsschichten](../CONFIG_MERGE_REFERENCE.md),
[Stages](../STAGES.md), [Tests](../TESTING.md) und der
[Referenz für ein Schwesterprojekt](../REFERENCE_FOR_KICLI_ASSIST.md).
Die übrigen Beispiele in diesen Dokumenten benötigen eine eigene Prüfung.
