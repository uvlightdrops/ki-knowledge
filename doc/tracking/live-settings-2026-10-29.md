# Live-Konfiguration: Umsetzung und Providerprüfung

Stand: 2026-10-29. Dieser Bericht unterscheidet implementierte Schnittstellen,
isoliert geprüfte Funktionen und tatsächlich erreichbare Anbieter.

## Architektur

Der bisherige read-only Settings-Auszug wurde durch die gemeinsame,
schema-basierte Widgetkit-Oberfläche ersetzt. ki-knowledge definiert keine
zweite Liste von editierbaren LLM-/Jira-/InfoSite-Feldern mehr.

- `ki_core.runtime_settings.RuntimeSettings`: Konfigurationsinventar,
  Layer-Auflösung, Schema-/Typprüfung, Revisionsschutz und Speicherung.
- `widgetkit_django.runtime_settings`: Django-Darstellung und
  Superuser-/CSRF-Schutz.
- `django_site/live_settings.py`: Projektroot, DB-Eigentümer,
  Aktivierungsgrenzen und Navigationsverweise.
- `llm_provider.py`: schlanker Adapter der `AppConfig`-Attribute auf
  `ki_core.chat`; keine zweite Provider-Erzeugung.

Die Settings-Übersicht zeigt jetzt tatsächliche aufgelöste Werte statt
hartcodiertem Provider, Datenpfad und InfoSite-Status. Der AppConfig-Cache
berücksichtigt Änderungen von `KI_STAGE` und `KI_PROFILE` zusätzlich zu den
Konfigurationsdateien und `KI_CFG_*`.

Providererzeugung, Modellabfrage und Timeout-/TLS-Optionen sind zentral.
Insbesondere erhält auch Ollama den konfigurierten HTTP-Timeout. Fehlende
Remote-Credentials und leere Endpunkte werden vor einem Netzwerkaufruf
abgewiesen. Fehler in der Modellabfrage sind keine erfolgreiche leere Liste;
die betroffene Prompt-Oberfläche meldet den Ausfall ausdrücklich.

## Nachweise in ki-knowledge

**172 gezielte Python-Tests bestanden**, gemeinsam ausgeführt:

- Live-Settings und vorhandener Sync-Konfigurationseditor.
- Alle vier Providerpfade einschließlich Auth-Header, Modell,
  Endpunktabgrenzung, Timeout/TLS sowie Sync-/Streaming-Protokollen.
- Explizite Timeout- und Fehlkonfiguration ohne stilles Failover.
- Speichern im Runtime-Layer und Verwendung durch den nächsten App-Client.
- Secret-Redaktion, Superuser-/CSRF-Grenzen, DB-Eigentümer,
  Nextcloud-Domainmapping und strukturierte Hostliste.
- AppConfig-Cache, Domain Chat, Textwerkstatt, KI-Vorschläge,
  Modulgrenzen und Paketinhalt.

Im gemeinsamen Unterbau bestanden separat **65 ki-core-Tests**,
**23 Wizard-Tests** und **21 Widgetkit-Tests**. Die vollständige
ki-core-Testkollektion ist damit nicht behauptet: zwei vorhandene
Testmodule benötigen dort nicht verfügbare optionale Abhängigkeiten.

**9 echte Browserabläufe bestanden**, mit temporärer Django-Datenbank und
separatem Konfigurationsprojekt, nicht mit den Live-Dateien:
zwei Settings-Abläufe sowie die sieben vorhandenen Werkstatt-Abläufe.
Die beim ersten Lauf falsch angenommenen Formularselektoren wurden an das
tatsächliche gemeinsame Mehrfeldformular angepasst.

Der letzte gemeinsame Browserlauf prüfte den fertigen Write-only-/PRG-Stand:
typisierte Text-/Listen-/Enum-/Boolwerte,
Reload ohne POST-Wiederholung, Credential-Speichern ohne Klartext-Rückgabe,
separater Credential-Konflikt und ausdrücklich bestätigtes Entfernen.

Schema-definierte Zugangsdaten können jetzt über getrennte Write-only-Formulare
in die projekteigene `creds.yaml` geschrieben werden. Sie besitzen einen
eigenen Revisionsschutz; bestehende Werte werden niemals ins Formular
zurückgegeben. Das ist keine projektübergreifende Credential-Synchronisierung.

Django-Systemcheck ohne Befund; Migrations-Dry-Run ohne neue Änderungen.
Keine Live-Datenbank wurde dafür migriert.

## Echte Providerproben in ki-knowledge

Es wurden ausschließlich kurze synthetische Aufforderungen ohne Quellcode,
Buchtext oder Repository-Kontext verwendet. Pro Anbieter wurden normale
Antwort und Streaming geprüft. Die aktive Providerwahl wurde nicht geändert;
die Probe überschreibt die Auswahl nur im eigenen Client-Snapshot.

| Provider | Normal | Streaming | Befund |
| --- | --- | --- | --- |
| mock | erfolgreich | erfolgreich | Lokaler Kontrollpfad |
| ollama | erfolgreich | erfolgreich | Tatsächliche Modellantwort |
| ki | nicht ausführbar | nicht ausführbar | Endpunkt, Modell und Schlüssel fehlen in der aufgelösten Projektkonfiguration |
| openai | nicht ausführbar | nicht ausführbar | API-Schlüssel fehlt in der aufgelösten Projektkonfiguration |

Die externen Pfade sind durch synthetische Protokolltests abgesichert.
Das ist **kein Nachweis einer erfolgreichen echten Remote-Modellantwort**.
Fehlende Zugangsdaten wurden weder erfunden noch aus einem anderen Projekt
kopiert. Die Providerproben haben keine Konfigurationsdatei verändert.

## Code-Assist-Anbindung und echte Gegenprobe

kicli-code-assist verwendet denselben Runtime-Dienst über `/api/settings`
und ein typisiertes React-Panel. Auch der TUI-Einstellungsdialog und die
Agent-Konfiguration verwenden den gemeinsamen Runtime-Speicher statt
eigenständiger Schreibwege.

Die Settings-API begrenzt Zugriff auf lokale Clients, prüft Host und
Origin/Referer und verlangt für Änderungen einen pro Serverprozess erzeugten
Token. Das ist eine lokale Administratorfunktion, keine freigegebene
Remote-Konfigurations-API. Die Token-/Hostgrenze ersetzt keine allgemeine
Benutzerverwaltung.

Der getrennte Endpunkt `/api/settings/secrets` verwendet denselben
Zugriffsschutz und ausschließlich Write-only-Änderungen mit eigener Revision.

Die Code-Assist-Anbindung wurde abschließend mit **108 gezielten
Settings-/Provider-/TUI-Tests** geprüft. Zusätzlich bestanden **24
Browserprüfungen** gegen ein isoliertes Projekt, einschließlich Credential-
Redaktion, Persistenz, Entfernen, Dateimodus und Token-Grenzen. Die vollständige
Code-Assist-Suite wurde außerdem gegen ihren vorhandenen Ausgangszustand
verglichen: weiterhin **37 Fehler und 18 Collection-/Setupfehler** in bereits
vorhandenen Fehlergruppen. Ein bestehender roter Gesamtstand ist kein grüner
Gesamtnachweis. Zwei eng begrenzte TypeScript-Typkorrekturen im FileBrowser
beseitigen die Buildblocker; `npm run build` ist erfolgreich.
Die generierten Dateien liegen in `web/static/`; der vorhandene
Flask-Entwicklungsbetrieb erwartet weiterhin Vite für die Oberfläche.

Die zusätzliche echte Probe verwendete
`kicli_code_assist.llm_runtime.LiveConfig` und `chat_client`, wiederum mit
synthetischem Inhalt und ohne Konfigurationsdateien zu verändern:

| Provider | Normal | Streaming | Befund |
| --- | --- | --- | --- |
| mock | erfolgreich | erfolgreich | Lokaler Kontrollpfad |
| ollama | erfolgreich | erfolgreich | Tatsächliche Modellantwort |
| openai | erfolgreich | erfolgreich | Tatsächliche Remote-Modellantwort mit Code-Assist-Konfiguration |
| ki | nicht ausführbar | nicht ausführbar | Erforderliche Providerkonfiguration fehlt |

Ein erfolgreicher OpenAI-Test in Code Assist ersetzt nicht den fehlenden
Schlüssel in ki-knowledge. Die Programme verwenden bewusst ihre jeweilige
Konfiguration; es gibt keinen stillen projektübergreifenden Credential-Import.

## Aktivierungs- und Eigentümergrenzen

Nicht jede Einstellung ist technisch gefahrlos hot-reload-fähig. Neue
LLM-Clients verwenden neue Werte; laufende Aufgaben behalten ihren Client.
Django-Startwerte, Datenpfade, Embedding-Modell und Stackdefinitionen sind
gesondert gekennzeichnet. Speichern verschiebt keine Daten und ersetzt
keinen notwendigen Neustart oder Reindexierung.

NodeConfig bleibt in der Sync-Administration, Widgetlayouts im Builder.
Der Konfigurationseditor gibt dafür keinen zweiten widersprüchlichen
Schreibweg frei.

Die anschließend gewünschte zusätzliche kompakte Tabellenansicht ist
am 30.10. als **C2** unter `/settings/config/c2/` ergänzt: Menüeintrag direkt
neben Configuration, eingerückte Tabellenhierarchie, kleine typgerechte
Eingaben, farbige Statuskürzel und Tooltips. Die ausführliche Ansicht bleibt
erhalten. C2 nutzt dieselben Rechte, Revisionen und Write-only-Credentialaktionen;
ein zusätzlicher echter Browserablauf prüft Speichern, Konflikt, Wechsel
zwischen beiden Ansichten, Secret-Redaktion und mobile Tabellenbegrenzung.
Die kompakte Django-Darstellung liegt im gemeinsamen Widgetkit-Paket;
Code Assist erhält dadurch noch keine kompakte React-Ansicht.

Schema-lose Einstellungen wie die aktuelle `stack`-Definition und
`knowledge.observation` erscheinen als schreibgeschütztes Inventar ohne
Wertausgabe. Sie sind **noch nicht über das Formular editierbar**.
Das ist eine sichtbare Abdeckungsgrenze und kein vermeintlich erfolgreicher
Speichervorgang: für eine spätere Bearbeitung zuerst einen verbindlichen,
ausreichend präzisen Schema-Vertrag ergänzen.

In Code Assist bleibt außerdem `prompts` schreibgeschützt: die bestehende
App-Struktur `prompts.active_role` widerspricht dem Basisschema. Die Umsetzung
kaschiert diesen Konflikt nicht durch unvalidiertes Schreiben. Damit ist eine
vollständige Bearbeitbarkeit **sämtlicher** Alt-Konfigurationsstrukturen noch
nicht erreicht.

Die Credential-Bereinigung bereits existierender Code-Assist-Dateien und die
Zugriffshärtung der unabhängigen Serversteuerungsrouten waren nicht Teil des
Settings-Schreibpfads. Bestehende Schlüssel wurden weder verschoben noch
projektübergreifend kopiert. Dieser Bericht ist keine Sicherheitsfreigabe
der gesamten Webanwendung.

## Bereitstellung

Änderungen liegen uncommitted in ki-knowledge, ki-core, widgetkit-django,
yaml-cfg-wizard und kicli-code-assist. Die gemeinsamen Pakete müssen zusammen
bereitgestellt werden; ein isoliertes Update nur von ki-knowledge reicht nicht.
In dieser Arbeitsumgebung sind die Geschwister editierbar angebunden.

Die laufenden Anwendungsserver wurden nicht neu gestartet und die echten
Projektkonfigurationen nicht geändert. Für die erstmalige Codeaktivierung
Django/Code Assist neu starten, bei Vite gegebenenfalls die Oberfläche neu laden.
Nach dieser Aktivierung benötigen die als live gekennzeichneten Werte keinen
erneuten Serverneustart. Keine zusätzliche Django-Migration ist erforderlich.

[Bedienung](../guides/live-settings.md) ·
[Projektübergreifende Architektur](../../../../dev_doc/architecture/live-runtime-settings.md)
