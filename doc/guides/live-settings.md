# Live-Konfiguration

Stand: 2026-10-29.

## Einstieg

**Settings → Live-Konfiguration** (`/settings/config/`) ersetzt die bisherige
schreibgeschützte Auswahl einzelner `AppConfig`-Attribute. Zugang haben nur
angemeldete, aktive Superuser. Die Einstellungen gelten für den ganzen
Projektprozess, nicht nur für die gerade ausgewählte Domain.

Die Oberfläche entsteht aus dem zusammengeführten ki-core-/Projektschema.
Neue fachliche Einstellungen deshalb im Projektschema definieren, statt
einen weiteren eigenen Formularkatalog anzulegen. Nicht definierte oder
unsicher darstellbare Strukturen dürfen nicht als beliebiger Roh-YAML-Baum
bearbeitet werden.

## Speichern und Vererbung

Nicht geheime Änderungen landen in `config/runtime/runtime.yaml`. Die Datei
ist host-lokal und gehört nicht ins Repository. „Entfernen“ nimmt nur den
Override zurück; es löscht weder den Schema-Default noch den darunterliegenden
Stage-Wert. Ein leerer Text ist etwas anderes als das Entfernen.

Rangfolge, niedrig nach hoch:

1. Schema-Defaults und `config/defaults/`.
2. `ki.yaml`, aktives Profil, aktive Stage.
3. Runtime-Datei.
4. `KI_CFG_*`.
5. `creds.yaml`.

Ein gespeicherter Override muss deshalb nicht der wirksame Wert sein.
Insbesondere Werte in `creds.yaml` und Prozess-Environment können ihn
überdecken. Die Oberfläche zeigt die Überlagerung an. Bestehende
Umgebungsvariablen lassen sich nicht durch das Schreiben einer YAML-Datei
im laufenden Prozess entfernen.

Jede Änderung prüft Feldtyp und Schema. Ein Revisionsvergleich verhindert,
dass ein alter Browserstand neuere Änderungen still überschreibt. Bei einem
Konflikt neu laden und die Änderung erneut prüfen. Speichern verwendet
Dateisperre und atomaren Dateiaustausch; Kommentare und ursprüngliche
YAML-Formatierung werden nicht erhalten.

## Zugangsdaten ohne Klartextanzeige

Schema-definierte Zugangsdaten haben separate **Write-only-Eingabefelder**.
Ein neuer Wert wird ausschließlich in die projekteigene `creds.yaml`
geschrieben; die Oberfläche liefert nie den bisherigen oder neuen Wert zurück.
Ein leeres Passwortfeld bedeutet keine Änderung. Das Entfernen eines
Credentials-Overrides ist ein gesonderter bestätigungspflichtiger Vorgang.
Danach kann wieder ein unterer Layer oder Environment-Wert gelten.

Die Credential-Datei besitzt einen eigenen Revisionsschutz und wird atomar
mit Dateimodus `0600` geschrieben. Eine außerhalb des Projekts aktive
Credential-Datei wird nicht still überschattet oder importiert.
DB-eigene Sync-Zugangsdaten bleiben ausgeschlossen.

Provider-Schlüssel werden vom nächsten neuen Client verwendet. Ein
Django-`secret_key`-Wechsel ist dagegen eine Neustart-/Sessionentscheidung;
ein Datenbank-DSN-Wechsel erfordert einen geplanten Verbindungswechsel.

## Was ist wirklich live?

| Bereich | Aktivierung |
| --- | --- |
| Chat-Provider, Modell, HTTP-Timeout/TLS | Nächster neu erzeugter Client; kein weiterer Serverneustart nach der Codeinstallation |
| InfoSite-/Jira-/Nextcloud-Einstellungen mit anfrageweiser Auflösung | Nächste Operation; bereits laufende Arbeit behält ihre eigene Konfiguration |
| Django-Startkonfiguration, Datenbank-/Speicherpfade, Embedding-Modell | Geplant speichern, betroffene Dienste neu starten und gegebenenfalls Datenmigration/Reindexierung durchführen |
| Ports, Prozesse, Container-/Stackdefinitionen | Betriebsänderung über stackctl; kein automatischer Neustart durch das Konfigurationsformular |

Ein Embedding-Modellwechsel macht vorhandene Vektoren nicht kompatibel:
Das ist kein harmloser Providerwechsel und erfordert eine geplante
Neuindizierung. Datenpfade nicht während laufender Importe umstellen.
Der Editor verschiebt keine Daten und migriert keine Datenbank.

Die Anzeige „Wirksam“ bezeichnet die aktuell aufgelöste Konfiguration,
nicht die rückwirkende Umkonfiguration bereits erzeugter Verbindungen,
Tasks oder Django-Settings.

## Andere Eigentümer

Node-Rolle, Aktivierung, Master-URL und Sync-Verhalten werden durch
`NodeConfig` in der **Sync-Administration** verwaltet. Die YAML-Oberfläche
gibt dafür keinen zweiten widersprüchlichen Schreibweg frei.
Die Node-ID bleibt außerhalb dieses Editors, da sie Identitäten und
Datenbankzuordnungen bestimmt.

Widget-Anordnung und -Breite bleiben im **Dashboard Builder**. Benutzer-/
Domainlayouts sind Datenbankobjekte und keine hostweiten YAML-Einstellungen.

## Gemeinsame Implementierung

`ki_core.runtime_settings.RuntimeSettings` übernimmt Auflösung, Feldinventar,
Validierung und Speicherung. `widgetkit_django.runtime_settings` stellt die
autorisierte Django-Oberfläche bereit. ki-knowledge ergänzt nur seine
Eigentümer- und Neustartgrenzen in `django_site/live_settings.py`.

kicli-code-assist verwendet denselben frameworkneutralen Kern über seine
Flask-/React-Oberfläche. Es braucht dafür weder Django noch ein zweites
Konfigurationsformat. Ein gemeinsamer Kern bedeutet nicht automatisch
gemeinsame Werte: Jedes Projekt behält seine eigenen Schichten und Secrets.

Der ältere begrenzte Sync-Editor bleibt unter `/settings/config/sync/`
erreichbar. Beide Oberflächen schreiben dieselbe Runtime-Datei; sie
erzeugen keine parallelen Konfigurationsspeicher.

## Kompakte Ansicht C2

Direkt neben **Configuration** steht **C2** (`/settings/config/c2/`).
Die zusätzliche Tabellenansicht nutzt dieselbe Konfiguration, Berechtigungen
und Revisionsprüfung wie die ausführliche Ansicht; diese bleibt unverändert.

Die erste Spalte bildet die Hierarchie durch Einrückung ab. Feldnamen und
Statuskennzeichen erklären sich per Tooltip: **N** Neustart, **L** live,
**W** wirksamer Wert, **R** Runtime-Override, **Ü** höherer Layer hat Vorrang,
**RO** schreibgeschützt. Bool-Werte sind farbig als Ja/Nein gekennzeichnet.
Farbe ist nur Zusatzinformation, nicht die einzige Statusanzeige.

Eingaben sind einzeilig und typgerecht kompakt. Strukturierte Werte bleiben
JSON; deren Textfeld kann bei Bedarf vergrößert werden. Zum Speichern
gewünschte Zeilen in „Ändern“ anhaken. „−R“ entfernt den Runtime-Override.
Zugangsdaten stehen separat mit kleinen Write-only-Eingabefeldern.
Auf schmalen Bildschirmen scrollt nur die Tabelle horizontal.

Die C2-Darstellung liegt wiederverwendbar in widgetkit-django; die
Code-Assist-/React-Ansicht wird durch diese zusätzliche Django-Seite nicht
verändert.
