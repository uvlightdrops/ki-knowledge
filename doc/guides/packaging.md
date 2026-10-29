# Paket-Build und kanonischer Quellbaum

Stand: 2026-10-28.

## Ein Quellbaum

`ki_knowledge/` ist der kanonische Python-Paketbaum. Setuptools entdeckt
ausdruecklich nur dieses Paket und seine Unterpakete, nicht beliebige
Verzeichnisse im Repository. Python-Unterpakete bekommen ein `__init__.py`.
Templates und statische Dateien werden als Paketdaten aufgenommen, nicht als
Namespace-Pakete.

Der zuvor getrackte Baum `src/ki_knowledge/integrations/` wurde entfernt:

- `jira_cache`, `jira_client`, `jira_csv` und `jira_graph` waren byte-identisch
  mit den aktiven Modulen.
- `jira_assistant` unterschied sich nur dadurch, dass die aktive Version ein
  fehlendes Chat-Backend behandelt. Dieses Verhalten bleibt unveraendert.
- Das alte `integrations/__init__.py` exportierte Klassennamen wie `JiraCache`
  und `JiraAssistant`, die die enthaltenen Module gar nicht bereitstellten.
- Es wurde kein Einstieg gefunden, der diesen zweiten Baum aktivierte.
  Es gibt deshalb keinen neuen Alias fuer `src.ki_knowledge`; der
  unterstuetzte Import bleibt `ki_knowledge.integrations`.

## Inhalt der Distribution

Der alte Build nahm mit `packages = ["ki_knowledge"]` nur die obersten Module
auf. Ein Editable-Checkout verdeckte dadurch fehlende CLI-/API-/Django-Pakete.
Die Distribution enthaelt jetzt:

- alle Python-Unterpakete, einschliesslich Management Commands und Migrationen;
- Django- und Wagtail-Templates sowie Django-CSS, JavaScript und Favicon;
- die Jinja-Templates unter `widgetkit_templates/`;
- die Standard-Kommandohierarchie `ki_knowledge/cli/cli.yaml`.

Die CLI nutzt weiterhin eine explizite `cli.yaml` im Arbeitsverzeichnis als
Override. Ohne Override verwendet sie die installierten Paketdefaults.
Ein vorhandener, aber defekter Override erzeugt eine Fehlermeldung mit Pfad;
er wird nicht still durch Defaults ersetzt.

**Nicht enthalten:** Projekt-/Hostkonfiguration, Stages, Schema im
Repository-Root, Zugangsdaten, Datenbanken, Tests, Examples und `kistack`.
Das Wheel ersetzt daher nicht das Betriebs-Checkout.
Die externe Konfigurationslinie bleibt unveraendert. Insbesondere brauchen
projektbezogene Entwicklungs-/Stackbefehle weiterhin das Checkout und dessen
Konfiguration; ihre gesamte Funktion ist nicht durch einen Paketimport belegt.

## Bauen und absichern

Aus einer eingerichteten Entwicklungsumgebung:

```bash
.venv/bin/python -m pip wheel --no-deps --wheel-dir dist .
.venv/bin/python -m pytest -q tests/test_packaging.py tests/test_cli.py
```

`tests/test_packaging.py` baut in einem temporaeren Quellverzeichnis erst eine
Source-Distribution und daraus ein Wheel. Es vergleicht alle Python-Dateien
und vorgesehenen Ressourcen mit dem Paketbaum und installiert dieses Wheel
nicht-editierbar in einer eigenen temporaeren Umgebung.

Imports werden ausserhalb des Checkouts mit isoliertem Python gestartet;
ihre Herkunft muss in dieser Installation liegen. Zusaetzlich startet die
installierte CLI mit `--help`, ohne eine `cli.yaml` im Arbeitsverzeichnis.
Vorhandene Dritt-/Schwesterpaket-Abhaengigkeiten der Entwicklungsumgebung
werden fuer diesen Offline-Test wiederverwendet. Das ist **kein Nachweis
einer vollstaendig frischen Dependency-Aufloesung** und kein Laufzeittest
aller Datenbank-/Webfunktionen.
