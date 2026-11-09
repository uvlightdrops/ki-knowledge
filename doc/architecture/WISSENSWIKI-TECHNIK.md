---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-08 18"
update_reason: "Netzzugriff und ausgelagerte Oberflächenressourcen ergänzt"
status: draft
semantic_blocks:
  - boundary
  - existing-parts
  - storage-and-identity
  - editing
  - proposals
  - agent-runtime
  - safety
  - first-slice
  - decisions
relations:
  - source: "#boundary"
    target: "WISSENSWIKI-ZUSAMMENARBEIT.md#shared-work"
    type: depends-on
    reason: "Die technische Skizze dient der beschriebenen gemeinsamen Arbeit."
  - source: "#proposals"
    target: "WISSENSWIKI-ZUSAMMENARBEIT.md#conversation-and-proposals"
    type: reference
    reason: "Die technische Vorschlagsbehandlung unterstützt den fachlichen Prüfablauf."
  - target: WISSENSWIKI-ZUSAMMENARBEIT.md
    type: reference
    reason: "Fachlicher Entwurf für Gespräch, Blöcke und Agentenfreiheit"
  - target: TEXT-AND-KNOWLEDGE-BLOCKS.md
    type: reference
    reason: "Begriffe, Herkunft und offene Fragen zum Wissensblock"
  - target: KNOWLEDGE-WORKBENCH-CONCEPT.md
    type: reference
    reason: "Älterer Werkstattentwurf als Vergleich, nicht als Vorgabe"
  - target: README.md
    type: parent
    reason: "Architekturübersicht"
---

# Wissenswiki: Technik

**Vorläufige Skizze:** Dieser Entwurf übersetzt die
[Idee der Zusammenarbeit](WISSENSWIKI-ZUSAMMENARBEIT.md) in prüfbare
technische Möglichkeiten. Ein erster lokaler Schreibweg besteht; Chat und
Agentenfunktionen sind weiterhin Vorschläge.

<a id="boundary"></a>
## Ziel und Grenze [boundary]

Ein kleiner lokaler Arbeitsraum könnte Blockbearbeitung, Beziehungen und
später ein kontextbezogenes Gespräch verbinden. Der Einstieg soll mit
wenigen Teilen funktionieren; ein Agentensystem, Graphdatenbank oder
verteilte Infrastruktur sind dafür nicht vorausgesetzt.

Die Oberfläche kann bestehende Markdown-Dokumentation lesend nutzen, ohne
deren Abschnitte ungeprüft zu fachlichen Wissensblöcken zu erklären. Ob
bestimmte Inhalte später übernommen werden, ist eine gesonderte Entscheidung.

<a id="existing-parts"></a>
## Vorhandene Ausgangspunkte [existing-parts]

Der lokale [`doc_viewer`](../../ki_knowledge/doc_viewer.py) liest
Markdown-Dateien mit YAML-Header und zeigt H2-Abschnitte und ausgehende
Relationen. Ohne zusätzliche Option bleibt er lesend. Mit `--workspace`
ergänzt er eine getrennte Oberfläche für eigene Blöcke; ein Chat besteht
nicht. Dokumentationsabschnitte werden dadurch nicht automatisch übernommen.

Das Projekt besitzt außerdem eine
[Textwerkstatt](KNOWLEDGE-WORKBENCH-CONCEPT.md) mit einem anderen
Quellen- und Markierungsschwerpunkt. Deren vorhandene Teile sind vor einer
Übernahme konkret zu prüfen, statt eine parallele Umsetzung oder vollständige
Wiederverwendbarkeit vorauszusetzen. Der bestehende
[`llm_provider`](../../ki_knowledge/llm_provider.py) ist der projektspezifische
Einstieg zur Chat-Provider-Auswahl; er ist für sich genommen keine
Agentenlaufzeit und kein Vorschlagsspeicher.

<a id="storage-and-identity"></a>
## Speicherung und Identität [storage-and-identity]

Für den ersten Versuch wird ein bestehendes Arbeitsverzeichnis ausdrücklich
angegeben und getrennt vom Dokumentationsverzeichnis gehalten. Jeder eigene
Block liegt in einer Markdown-Datei mit einer zufälligen stabilen ID als
Dateiname. YAML enthält ID, optionalen Titel, die beim Anlegen menschliche
Formulierung sowie ausgehende Beziehungen und geordnete `parts`; der
Markdown-Text folgt dem Header.

Die Beziehung wird nur im Ausgangsblock gespeichert und verweist per ID auf
das Ziel. Die `parts`-Liste ist davon getrennt und erlaubt auch wiederholte
Bestandteile. Verschieben oder Umbenennen der Datei außerhalb der Anwendung
ist nicht unterstützt. Eine Datenbank wird nicht vorausgesetzt; das Format ist
ein erster Versuch, kein abschließend beschlossenes Wissensmodell.

<a id="editing"></a>
## Schreiben und Änderungen [editing]

Der Schreibdienst prüft IDs, Ziele und die Dateifassung und ersetzt jeweils
eine Datei atomar. Eine seit dem Laden geänderte Datei löst beim Speichern
einen sichtbaren Konflikt aus. Eigene Schreibvorgänge verwenden eine
gemeinsame Sperre; externe Editoren wie Typora nehmen daran nicht teil. Ein
gleichzeitiger externer Schreibvorgang im sehr kurzen Zeitraum zwischen
Fassungsprüfung und Ersetzen kann deshalb nicht sicher erkannt werden.

Es gibt noch keine Versionsgeschichte oder Rücknahme früherer Fassungen.
Git-Commits werden nicht automatisch erzeugt. Die Herkunft beim Anlegen ist
notiert, aber spätere Überarbeitungen werden nicht einzeln protokolliert.

<a id="proposals"></a>
## Gespräch und Vorschläge [proposals]

Ein Gespräch könnte ausgewählte Blöcke als ausdrücklich sichtbaren Kontext
verwenden. Vor einer Anfrage muss erkennbar sein, welche Inhalte an welchen
Provider gesendet werden; lokale und externe Modelle sind nicht gleichzusetzen.

Eine Antwort bleibt zunächst Gespräch. Ein Änderungsvorschlag sollte Ziel,
Text, Herkunft und Ausgangsfassung festhalten und gesondert prüfbar sein.
Annehmen darf nur nach menschlicher Bestätigung erfolgen; wenn sich die
Ausgangsfassung zwischenzeitlich geändert hat, muss erneut geprüft statt
blind überschrieben werden. Verwerfen darf bestätigte Inhalte nicht verändern.
Speicherung und Lebensdauer von Gespräch und Entwürfen sind noch offen.

<a id="agent-runtime"></a>
## Agenten und Grenzen [agent-runtime]

Mehrere Agenten wären später über einen gemeinsamen Auftrags- und
Vorschlagsablauf denkbar; die verfügbaren Copilot-CLI-Agenten sind damit
nicht automatisch in der Anwendung nutzbar. Auswahl der Laufzeit,
Anbindung und Rollen bleiben offen.

Für eigenständige Erkundung wären vorab begrenzter Arbeitsbereich,
erlaubte Aktionen, maximale Aufrufe oder Kosten sowie Abbruch und
Fehleranzeige nötig. Als erster Sicherheitsrahmen schreiben Agenten nur
prüfbare Entwürfe, nicht bestätigte Wissensblöcke. Mehr Autonomie wäre eine
eigene, gemeinsam zu prüfende Entscheidung.

<a id="safety"></a>
## Lokale Sicherheit [safety]

Der Server bindet standardmäßig an alle IPv4-Schnittstellen; mit
`--host 127.0.0.1` bleibt er lokal. Geräte verwenden die numerische IPv4-Adresse
des Servers; `localhost` funktioniert auf dem Server selbst. Der Schreibweg
prüft Host, Origin und ein pro Start erzeugtes Token gegen fremde
Browseranfragen; das Token ist **kein Zugangspasswort**. IDs und Blockdateien
werden eingegrenzt, symbolische Links als Blockdateien abgelehnt. Texte werden
als Text statt als HTML eingefügt.

Der Zugriff erfolgt ohne Anmeldung und unverschlüsselt. Alle Geräte, die den
Port erreichen, können die Dokumentation lesen und den Arbeitsraum ändern;
auch andere Netze sind bei entsprechender Routing- und Firewallkonfiguration
nicht ausgeschlossen. Ein Einsatz ist nur in einem vertrauenswürdigen Netz
geeignet. HTML, CSS und JavaScript liegen getrennt vom Python-Code in
`ki_knowledge/wiki_assets/` und werden mit dem Paket ausgeliefert.

<a id="first-slice"></a>
## Kleiner erster Arbeitsweg [first-slice]

Der erste Versuch ermöglicht zwei nebeneinander bearbeitbare Blöcke, eine
gerichtete Beziehung per Klick und geordnete Bestandteile mit Textvorschau.
Die [Startanleitung](../README.md#getting-started) beschreibt den Aufruf.
Eine KI-Antwort als prüfbarer Vorschlag ist noch nicht implementiert.

<a id="decisions"></a>
## Offene Entscheidungen [decisions]

Zu klären sind insbesondere die Weiterentwicklung von Speicherformat und
Identität, eine mögliche Einbindung in die bestehende Anwendung, Revisionen,
Aufbewahrung von Chat und Vorschlägen, Provider-Freigaben sowie Grenzen der
Agenten. Ein Austausch der Textwerkstatt ist nicht beschlossen.

**Arbeitsweg, 2026-11-08:** Viewer und Provider-Einstieg als Ausgangspunkte
gelesen; den ersten lokalen Arbeitsraum ergänzt. Weitergehende Abläufe sind
Vorschläge, keine Implementierungsprüfung der Textwerkstatt oder Agentenlaufzeit.
