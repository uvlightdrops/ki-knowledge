---
project: ki-knowledge
agent_project: ki-knowledge
scope: documentation
created: "2026-10-29 09"
updated: "2026-11-10 20"
update_reason: "Relocate shared documentation into doc/ and update references"
status: active
semantic_blocks:
  - getting-started
  - areas
  - agent-edits
  - shared-documentation
relations:
  - target: architecture/KI-KNOWLEDGE-KONZEPT.md
    type: reference
    reason: "Fachlicher Gesamtentwurf"
---

# Dokumentation: ki-knowledge

Die Dokumentation ist nach Zweck gegliedert. **Anleitungen, Konzepte und
historische Berichte sind nicht derselbe Implementierungsstand.** Bereichsbezogene
Altunterlagen werden schrittweise in den jeweiligen `archiv/`-Ordner verschoben;
das bestehende übergreifende Archiv bleibt erhalten.

**Jira:** Bestehende Jira-spezifische Funktionen und Dokumentationsabschnitte
sind Legacy. Ziel ist Jira als gleichberechtigtes Eingabe-/Importformat neben
anderen Quellen; daraus folgt keine Aussage über eine bereits fertige
Neugestaltung.

Knowledge Retrieval, Suche und Chat bleiben gewünschte Funktionen. Die
Kennzeichnung eines alten Jira-Pfads ist keine Ablehnung dieser Funktionen.

<a id="hier-anfangen"></a>
<a id="getting-started"></a>
## Hier anfangen [getting-started]

- [Ki-Knowledge: fachliches Konzept](architecture/KI-KNOWLEDGE-KONZEPT.md):
  gemeinsamer Zielbildentwurf mit Abgrenzung zum bisherigen System.
- Lokale, lesende Ansicht für Markdown-Blöcke und ihre Beziehungen:
  `.venv/bin/python -m ki_knowledge.doc_viewer`; anschließend
  `http://127.0.0.1:8765/` im Browser öffnen. Beenden mit `Strg+C`.
  Optional kann ein anderes Dokumentationsverzeichnis als Argument und der
  Port mit `--port` angegeben werden. Die Ansicht ändert keine Dateien;
  Dokumente ohne YAML-Header werden mit einer Fehlermeldung angezeigt.
- Arbeitsraum für eigene Blöcke und Dokumentationsdomäne starten:
  zunächst `mkdir -p ~/dev_wiki ~/dev_wiki_rel`, dann `./start-wiki` und
  `http://127.0.0.1:8765/workspace/` öffnen. Das Skript hinterlegt diese
  Verzeichnisse und nimmt weitere Viewer-Optionen entgegen, z. B.
  `./start-wiki --host 127.0.0.1`. Zwei Blöcke speichern,
  über die einklappbare Seitenleiste suchen und links oder rechts öffnen.
  In der Mitte Beziehungstyp und Richtung auswählen und verbinden; der rechte Block kann auch als
  geordneter Bestandteil des linken hinzugefügt werden. Es gibt noch keine
  Versionsgeschichte, keinen Chat und keine KI-Funktion. Eine parallele
  Bearbeitung derselben Datei in einem externen Editor ist zu vermeiden.
  Über **Wissensnetz** öffnet sich die separate animierte Ansicht:
  Blasen lassen sich ziehen und durch Anklicken als Ausgang und Ziel wählen.
  In „Farben und Richtung“ den Relationstyp anklicken; er wird nach Klick
  auf „Beziehung anlegen“ gespeichert.
  Die Blocktexte selbst sind dort nur lesbar. Die sieben Typen und Farben
  folgen `dev_doc/doc/documentation-guidelines/DOCUMENTATION_VISUALIZATION.md`;
  bereits vorhandene andere Typen bleiben sichtbar. Fehlende Ziele werden
  unter dem Netz genannt. Die Anordnung ist nicht gespeichert.
  Zusätzliche Dokumentdomänen lassen sich beim Start mehrfach angeben, je mit
  Namen, Quellverzeichnis und separatem bestehenden Beziehungsverzeichnis, z. B.:

  ```bash
  ./start-wiki --domain Weitere /pfad/zur/dokumentation /pfad/zu/beziehungen
  ```

  Oben in der Netzansicht wechseln die Domänenlinks zwischen Wiki und
  Dokumentation. Dokumente und ihre H2-Abschnitte werden lesend angezeigt,
  vorhandene YAML-Relationen bleiben unverändert. Neue Beziehungen werden in
  `dokument-beziehungen.json` im jeweiligen Beziehungsverzeichnis gespeichert.
  Abschnitte ohne eindeutige Block-ID sind sichtbar, können aber nicht als
  Ausgang oder Ziel neuer Beziehungen dienen. Verschobene Dokumente oder
  geänderte Block-IDs können Beziehungen unauflösbar machen. Eine Suche und
  Seitenwahl begrenzen die gleichzeitig animierten Blasen auf 60; bereits
  ausgewählte Blöcke können zusätzlich angezeigt werden.
  Neue Blöcke stehen nicht unter `/` (Dokumentationsansicht), sondern im
  Arbeitsraum unter `/workspace/` und als einzelne Markdown-Dateien in dem
  mit `--workspace` angegebenen Verzeichnis, beim Startskript `~/dev_wiki`.
  Ihr Dateiname ist die stabile Block-ID. Der Kopfbereich verlinkt
  Arbeitsraum, Dokumentation und Django-App; Django verlinkt zurück.
  Standardmäßig werden dieselbe IP-Adresse und die Ports 8000 (Django) bzw.
  8765 (Wiki) verwendet. Ein abweichendes Django-Ziel kann beim Viewer mit
  `--django-url` angegeben werden. Der Django-Link erscheint für `localhost`
  und numerische IPv4-Adressen und setzt den Wiki-Standardport 8765 voraus.
  Der Server bindet standardmäßig an alle IPv4-Schnittstellen. Andere Geräte
  erreichen ihn unter `http://<IPv4-Adresse-des-Rechners>:8765/workspace/`;
  die IP-Adresse kann man mit `hostname -I` ermitteln. **Ohne Passwort und
  ohne HTTPS** können alle erreichbaren Geräte Inhalte lesen und ändern;
  Firewall und Netzwerk bestimmen die Erreichbarkeit, nicht die Anwendung.
  Nur in einem vertrauenswürdigen Netz betreiben. Mit `--host 127.0.0.1`
  bleibt der Zugriff auf diesen Rechner beschränkt.
- Temporäre Brücke: `./start-wiki --ki-domains` zeigt die Markdown-Domänen
  der Django-App im Wissensnetz; `.venv/bin/python -m ki_knowledge.wiki_bridge
  link-wiki` macht `~/dev_wiki` in Django als Domäne `dev-wiki` sichtbar.
  Details und Rückbau: `~/dev_doc/doc/wissenswiki/BEDIENUNG.md` (Abschnitt
  `bridge`).
- [Weiterentwicklung von ki-knowledge](architecture/WEITERENTWICKLUNG.md):
  Optionen von Integration bis Neuentwicklung, Empfehlung und Migrationspfad.
- [Django, Wagtail und Widgetkit](architecture/DJANGO-WAGTAIL-WIDGETKIT.md):
  technischer Überblick über die bestehende Webanwendung und ihre Grenzen.
- [Schnellstart und Projektueberblick](../README.md).
- [**Deployment-Infrastruktur**](deployment/README.md) — Stages, Config-Merge, Betrieb.
- [Bestandsaufnahme vom 28.10.2026](tracking/project-inventory-2026-10-28.md):
  Ausgangslage mit Nachtraegen zu einzelnen Bereinigungsschritten.
- [Kurzinventur vom 29.10.2026](tracking/project-inventory-followup-2026-10-29.md):
  Stand nach den Strukturarbeiten und E4; keine aktuelle Gesamtpruefung.
- [Service- und Views-Refactoring](refactorings/views-module-architecture.md):
  Modulzustaendigkeiten, Kompatibilitaetsfassaden und weitere Grenzen.
- [Django und Service-Stack betreiben](guides/DJANGO_DEV.md).
- [Konfiguration administrieren](guides/YAML_CONFIG_SYSADMIN.md).
- [Paket-Build und Quellbaum](guides/packaging.md).
- [Quellen, Workspace und Output unterscheiden](architecture/SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md).
- [Textwerkstatt-Konzept](architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md) und
  [Editor-Entwurf als Markdown](features/knowledge-workbench-design.md) —
  Zielbild für persistente Markierungen, Relationen und KI-Überarbeitung.
  Die [Textwerkstatt-Anleitung](guides/text-workbench.md) beschreibt die erste
  Umsetzung E0–E4 sowie Archiv und Zeilennavigation vom 30.10.2026.
- [Vollstaendiger Dokumentindex](INDEX.md).

<a id="bereiche"></a>
<a id="areas"></a>
## Bereiche [areas]

| Bereich | Inhalt und Verbindlichkeit |
|---|---|
| [architecture/](architecture/README.md) | Modelle, Systemgrenzen und fachliche Konzepte; Status im jeweiligen Dokument beachten. |
| [guides/](guides/README.md) | Bedienung, Betrieb und Entwicklung dieses Projekts. |
| [deployment/](deployment/README.md) | Deployment- und Betriebshinweise; ältere Beispiele einzeln prüfen. |
| [features/](features/README.md) | Fachfunktionen, Beispiele und Anforderungen; keine pauschale Fertigmeldung. |
| [integration/](integration/README.md) | Anbindung externer Systeme und Schwesterpakete. |
| [refactorings/](refactorings/README.md) | Umbaukonzepte und Migrationsplaene; nicht automatisch umgesetzt. |
| [tracking/](tracking/README.md) | Datierte Bestandsaufnahmen und detaillierte Abdeckungsberichte. |
| [archive/](archive/README.md) | Historische Berichte, ueberholte Roadmaps und Jira-Legacy. |

Befehlsbeispiele gelten relativ zum Repository-Root.

<a id="agent-edits"></a>
## Agentenbearbeitung und Prüfstand [agent-edits]

Die gemeinsamen Dokumentations-Skills gelten für diesen gesamten Baum,
einschließlich der Archive. Eine semantische ID oder der Status `active` ist
kein Nachweis, dass eine Aussage fachlich oder technisch aktuell ist.
Entwürfe, historische Inhalte und noch ungeprüfte Aussagen bleiben als solche
kenntlich; bestätigte menschliche Entscheidungen werden nicht stillschweigend
durch Agentenvorschläge ersetzt.

Agenten dokumentieren wesentliche Änderungen mit Datum, Anlass und Prüfumfang
im betroffenen Dokument oder in einem verlinkten Bestandsbericht. Sie nennen
offene fachliche Fragen und kennzeichnen Vorschläge, statt erfundene
Verifikationsdaten oder pauschale Vertrauenswerte einzutragen. Bereits
committierte Fassungen bleiben in Git nachvollziehbar, ausgelagerte Inhalte
im zuständigen Archiv.
Ausdrücklich als geschützt gekennzeichnete Bereiche werden nicht ohne
entsprechende menschliche Freigabe verändert; eine solche Sperre wird nicht
nachträglich für ungeprüfte Inhalte behauptet.

Die [Bestandsaufnahme](tracking/DOKUMENTATIONSBESTAND-2026-11-08.md) hält
den Umfang der bisherigen Prüfung und die nächsten offenen Schritte fest.

<a id="gemeinsame-dokumentation"></a>
<a id="shared-documentation"></a>
## Gemeinsame Dokumentation [shared-documentation]

Fuer die Arbeit mit KI-Agenten gelten die gemeinsamen Skills aus
`~/dev_doc/skills`, darunter Standards fuer Dokumentation, Codequalitaet,
Tests und Git-Workflows. Lokal sind sie ueber `.github/skills` im
Projekt-Root eingebunden; der ignorierte Symlink muss bei Bedarf auf einem
neuen Rechner eingerichtet werden:

```bash
mkdir -p .github
ln -s ~/dev_doc/skills .github/skills
```

- [Server-Management](../../../dev_doc/doc/server-mngm/SERVER_MANAGEMENT_README.md).
- [Gemeinsame CLI-Architektur: historische Entwuerfe](../../../dev_doc/doc/cli-management/README.md).
- [Kanonische YAML-Betriebsanleitung](../../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md).

Die externen Verweise setzen das bekannte Workspace-Layout voraus; sie sind
nicht Bestandteil eines alleinstehenden ki-knowledge-Checkouts. `doc/link`
bleibt als vorhandener lokaler Daten-Symlink unveraendert und ist kein Teil
dieses Dokumentationsbaums.
