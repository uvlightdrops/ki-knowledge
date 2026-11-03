---
project: ki-knowledge
scope: deployment
created: "2026-11-02 22"
updated: "2026-11-02 22"
update_reason: "Umsetzungsplan fuer rootloses Uberspace-8-Hosting im KI-Oekosystem"
status: draft
agent_project: ki-knowledge
---

# Uberspace 8: Deployment-Umsetzung

## Status und Geltungsbereich

Ziel ist ein **Uberspace-8-Hosting-Account ohne Root-Zugriff**, kein eigener
Ubuntu-VPS. Dieses Dokument ist der erste Umsetzungsschritt: Architektur,
Skriptverantwortlichkeiten, Voraussetzungen und Abnahme. Die beschriebenen
neuen Skripte, Stage und stackctl-Erweiterungen sind **noch nicht implementiert**;
auf einem Zielhost wurde nichts installiert oder gestartet.

Einstiege: [Deployment](README.md), [Dokumentationsbaum](../README.md),
[Config-Merge](CONFIG_MERGE_REFERENCE.md). Projektuebergreifende Grundlagen:
[Server-Management](../../../../dev_doc/server-mngm/SERVER_MANAGEMENT_README.md)
und [KI-Oekosystem](../../../../dev_doc/architecture/ki-ecosystem-workbench.md).
Externe Workspace-Links setzen benachbarte Repositories voraus.

## 1. Bestehende Linie und notwendige Anpassungen

Beibehalten werden Git-Transport per HTTPS, Geschwister-Repositories,
projektbezogene `.venv`, Konfiguration durch ki-core und **stackctl als einziger
Lifecycle-Einstieg**. Keine Makefiles, duplizierten `.env`-Konfigurationen,
eigenen PID-Register oder projektspezifischen Ersatz-Prozessmanager.

Es gibt einen konkreten Dokumentations-/Integrationskonflikt:
`ki-knowledge/README.md` und `kistack` verwenden noch das globale stackctl;
die aktuelle `stackctl/README.md` verlangt im KI-Oekosystem dagegen
`.venv/bin/python -m stackctl`, wobei `install` in die ausfuehrende venv
installiert und keine Projekt-venv anlegt. Vor dem Bootstrap diesen Vertrag
anhand der verwendeten stackctl-Revision pruefen und die betroffenen
Einstiegspunkte samt Launcher-Tests konsistent anpassen. Kein stiller Wechsel
zwischen Tool- und Projektumgebung.

Die vorhandene `prod`-Stage bleibt unveraendert: sie beschreibt Hostbetrieb
mit Docker Compose und Django `runserver`. Uberspace bekommt eine eigene
Stage `prod-uberspace8`. Ein Stage-Wechsel allein macht aus dem bestehenden
lokalen Prozessbackend noch keine systemd-Integration.

## 2. Verifizierte Uberspace-8-Rahmenbedingungen

| Bereich | Bedeutung fuer die Umsetzung |
|---|---|
| Betriebssystem | Arch Linux mit Rolling Releases; keine `apt`-/`sudo`-Installation voraussetzen. |
| Dauerbetrieb | systemd-User-Instanz startet beim Hostboot; `supervisord` gehoert zu Uberspace 7, nicht 8. |
| Web | Uberspace-Caddy uebernimmt HTTPS und Routing. Das Webbackend muss auf `0.0.0.0` oder `::` lauschen, Port 1024–65535. |
| Python | Versioniertes Binary fuer Bootstrap verwenden; vorgeschlagen Python 3.12, Paketkompatibilitaet auf dem Zielhost pruefen. Nicht den wechselnden Standardinterpreter voraussetzen. |
| Ressourcen | Laut aktuellem U8-Handbuch insgesamt 1500 MiB RAM, CPU-Fair-Use und standardmaessig 10 GB Speicher. Tatsaechliche Account-Limits vor Installation messen. |
| PostgreSQL | Vom Anbieter bereitgestellt; eigene Datenbank mit Account-Praefix moeglich. Zugang ueber localhost, Passwort in privater `~/.pgpass`. |
| Erweiterungen | pgvector ist in der gelesenen U8-Dokumentation nicht zugesichert. Verfuegbarkeit und Berechtigung muessen vorab bestaetigt werden. |

Diese Aussagen stammen aus dem **U8-Handbuch**, nicht aus U7-Anleitungen.
Rolling Releases und Anbieterlimits bei der eigentlichen Installation erneut
pruefen; die unten verlinkten Quellen sind keine Zusage fuer jeden Account.

## 3. Zielaufbau und offene Freigaben

```text
Browser -- HTTPS --> Uberspace-Caddy
                       | /static -> DocumentRoot, nur oeffentliche Assets
                       | /       -> Django WSGI auf 0.0.0.0:<web-port>
                                         |
                              interne Knowledge-API auf 127.0.0.1:<api-port>
                                         |
                            explizit konfigurierter Daten-/Providerzugriff

stackctl -> systemd --user -> benannte Services und Journal
ki-core  -> defaults -> ki.yaml -> Profil/Stage -> runtime -> KI_CFG_* -> creds
```

Vorgeschlagen: Gunicorn statt `runserver --insecure`, zunaechst ein Worker
mit begrenzter Parallelitaet; API ohne Reload. Kein eigener nginx und kein
Docker-/Helm-Stack auf diesem Account. Gunicorn ist derzeit keine
Projektdependency und muss bei Umsetzung explizit aufgenommen werden.

**Vor Implementierung der betroffenen Skripte entscheiden:**

| Entscheidung | Vorschlag / Grenze |
|---|---|
| Datenbank | Anbieter-PostgreSQL nur bei nachgewiesenem pgvector-Support fuer den KnowledgeStore. Andernfalls explizit SQLite-Pilot oder externe PostgreSQL-Datenbank vereinbaren. |
| Embeddings | Ollama mit `nomic-embed-text` auf einem separaten erreichbaren Host; keine lokale Modellinstallation im knappen Accountbudget. Verbindung ueber abgesicherten Zugang/Tunnel, nicht eine offene Ollama-API. |
| Chat | Vorhandenen Provider ueber `ki_knowledge.llm_provider` / ki-core konfigurieren; Endpoint und Zugang auf dem Zielhost pruefen. |
| Zugriff | Pilot zunaechst nur fuer berechtigte Nutzer; oeffentliche Inhalte und administrative Schreibaktionen vor Freischaltung getrennt pruefen. |
| Domain und Updates | Eigene Subdomain, freie Ports und auszuliefernde Branches je Repo festlegen. Erst manueller Git-Updatepfad, spaeter opt-in Automatik. |

Der aktuelle KnowledgeStore fuehrt bei PostgreSQL
`CREATE EXTENSION IF NOT EXISTS vector` aus. Ein erfolgreicher Django-DB-Test
allein reicht deshalb **nicht** als Nachweis des vollstaendigen Betriebs.
Ein SQLite-Pilot ist eine bewusst freigegebene Variante, kein automatischer
Fallback bei PostgreSQL-Fehlern. Ein bestehender PostgreSQL-Datenbestand braucht
eine gesonderte, gepruefte Migration; DSN leeren migriert keine Daten.

## 4. Eigentuemermodule und geplante Artefakte

| Ort | Geplante Verantwortung |
|---|---|
| `stackctl` | Generischer systemd-User-Adapter fuer Installieren/Starten/Stoppen/Status/Logs; gleiche aufgeloeste Service-Spec, keine Knowledge-Logik. |
| `ki-core` | Unveraenderter Config-Loader und Providervertrag; keine Uberspace-Sonderkonfiguration daneben. |
| `config/stages/prod-uberspace8.yaml` | Projekt-Spec: keine Compose-Dienste starten, WSGI-Kommando, interne API, Reload aus, Debug aus; benoetigte generische Spec-Felder zuerst in stackctl definieren. |
| `schema/ki_knowledge.schema.yaml` und Django-Settings | Explizite konfigurierbare HTTPS-/CSRF-/Cookie-Einstellungen sowie Static-/Media-Pfade; Defaults bestehender Stages bewahren. |
| `pyproject.toml` | WSGI-Abhaengigkeit und vereinbarter stackctl-Installationsvertrag; keine absoluten Entwicklerpfade. |
| `deploy/uberspace8/bootstrap.py` | Rootlosen Erstaufbau pruefen, Projekt-venv mit gewaehltem Python erstellen, stackctl darin bereitstellen und dessen Sibling-Installation aufrufen. Keine Lifecycle-Implementierung. |
| `deploy/uberspace8/configure_web.py` | Nur freigegebene Domain-/Pfad-Backends ueber die U8-CLI konfigurieren; vorher Bestand anzeigen, keine fremden Backends ueberschreiben. |
| `deploy/uberspace8/update.py` | Gesperrte Update-Transaktion: Git-Pruefung, Backup, freigegebene Revisionen, Installation bei Bedarf, Migration, Assets, Neustart und Readiness ueber stackctl. |
| `tests/` | Bootstrap-/Update-Fehlerpfade und Projekt-Spec; Adapter-/Unit-Tests gehoeren ins stackctl-Repo. |

Dateinamen sind geplante Artefakte, keine bereits aufrufbaren Befehle.
Die Adapter-CLI erst nach Abstimmung der stackctl-Spec dokumentieren:
insbesondere kein erfundenes `stackctl -t uberspace` oder bereits vorhandenes
systemd-Ziel behaupten.

Skripte vorzugsweise als Python mit `subprocess`-Argumentlisten, klaren
Exitcodes und begrenzten Timeouts, nicht als lange eingebettete Python-Bloecke
in Shellskripten. Idempotent arbeiten; fehlende Programme/Konfigurationen
konkret melden. Keine stillen Defaults, kein `eval`, kein Secret im Log.

## 5. Konfiguration, Dateien und HTTPS

Vorgeschlagenes Hostlayout, vom konkreten Entwicklerpfad unabhaengig:

```text
~/ki/src/ki-knowledge/                  Checkout und .venv
~/ki/src/stackctl/                      unabhaengiges Tool-Checkout
~/ki/src/<siblings>/                    Namen/Pfade aus pyproject.toml
~/ki/data/ki-knowledge/                 Daten, Quellen, Workspace, private Medien
~/ki/backups/ki-knowledge/              gesicherte Backups und Revisionsmanifest
~/.config/systemd/user/                 von stackctl verwaltete Units
/var/www/virtual/<account>/<docroot>/static/  collectstatic-Ausgabe
```

Nichtgeheime Hostwerte in `config/runtime/runtime.yaml`; Secrets in
`creds.yaml` mit Modus `0600` bzw. bei PostgreSQL passende private `.pgpass`.
Beide Konfigpfade und `.active_stage` sind bereits gitignored. Keine Kopie
von Zugangsdaten in Units, `.env` oder Dokumentation. Relative/expandierte
Pfade ueber den Config-Vertrag aufloesen; `${HOME}` in YAML nicht ohne
nachgewiesene Loader-Unterstuetzung verwenden.

Die Stage muss `debug: false` und explizite `allowed_hosts` erzwingen.
DSN, API-URL, Provider-URL, Datenroot und Wagtail-Admin-URL muessen im
**aufgeloesten** Configstand stimmen: `ki.yaml` und `creds.yaml` koennen
Stagewerte ueberlagern. Systemd-WorkingDirectory ist das Projektroot,
Interpreter die Projekt-venv, Stage explizit; keine interaktive Shellaktivierung.

Vor Freigabe Django um erforderliche Einstellungen erweitern:
`CSRF_TRUSTED_ORIGINS`, sichere Session-/CSRF-Cookies und gepruefte
HTTPS-Erkennung hinter dem Anbieterproxy. `SECURE_PROXY_SSL_HEADER` nur
setzen, wenn dessen Header vom Proxy verlaesslich bereinigt/gesetzt wird;
keine ungepruefte Vertrauensannahme oder Redirect-Schleife.

`STATIC_ROOT` ist aktuell im Quellbaum festgelegt. Fuer U8 konfigurieren
und `collectstatic` in den echten DocumentRoot schreiben; kein Symlink auf
das private Home-Verzeichnis. Nur oeffentliche Assets dort ablegen.
Wagtail-Medien separat behandeln: private Uploads nicht pauschal durch ein
oeffentliches `/media`-Backend freigeben.

U8-Beispiel, **erst nach Domainpruefung und laufendem Webdienst**, mit
freigegebenen konkreten Werten:

```bash
uberspace web backend list
uberspace web backend add <domain>/ port <web-port>
uberspace web backend add <domain>/static static
uberspace web backend list
```

Nicht blind `--force` verwenden; bestehende Zuordnungen muessen explizit
freigegeben werden. Knowledge-API und Datenbank bekommen kein Webbackend.

## 6. Implementierungsreihenfolge und Abnahme

1. **Host-Preflight und Entscheidungen:** Python, Git, User-systemd,
   Namespace, Ports, Quota und RAM pruefen; DB-/pgvector- und Providerzugang
   entscheiden. Noch keine Migration oder Routingaenderung.
2. **stackctl-Vertrag konsolidieren:** venv-Bootstrap und generischen
   User-systemd-Adapter implementieren. Unitnamen projektspezifisch,
   `WantedBy=default.target`, begrenzte Restarts, Journal, sauberes SIGTERM.
   Status/Logs auch fuer die bestehende maschinenlesbare Integration liefern.
   Keine parallel von stackctl und systemd verwalteten PID-Lebenszyklen;
   Vorbereitung genau einmal im festgelegten Start-/Updatepfad.
3. **Projekt integrieren:** Stage, WSGI-Dependency, HTTPS-/Asset-Settings und
   Bootstrap implementieren; erforderliche Schema-/Config-Tests ergaenzen.
   External-Dienste weder starten noch stoppen; keine geerbten Compose-Hooks
   oder Ollama-Model-Pulls ausfuehren.
4. **Pilot installieren:** Backups vorbereiten, Migration/KnowledgeStore
   pruefen, Assets sammeln, Dienste ueber stackctl starten; Routing erst nach
   lokaler Readiness konfigurieren. Adminzugang interaktiv anlegen.
5. **Updatepfad umsetzen:** Schreibende Dienste/Jobs geordnet pausieren,
   konsistente Sicherung erstellen, genehmigte saubere Checkouts per
   `git pull --ff-only` aktualisieren. Kein automatisches Stash, Reset,
   Branchwechsel oder Umschreiben der Historie. Jede Sibling-Revision und
   aufgeloeste Paketversion im privaten Revisionsmanifest festhalten.
6. **Automatisierung freigeben:** Erst nach erfolgreichem Wiederherstellungstest
   denselben Updatepfad als opt-in User-Timer oder kontrollierten SSH-Aufruf
   betreiben. Nicht jeder beliebige Push loest ungepruefte Prod-Migrationen aus.

Bei Fehlern Update mit ungleich null beenden und den tatsaechlichen Zustand
melden; keine Erfolgsmeldung nach fehlgeschlagener Migration oder Readiness.
Keine automatische Rueckmigration: Rueckkehr zu alten Coderevisionen nur bei
kompatiblem Schema, sonst dokumentierte Wiederherstellung der gesicherten
Daten und Revisionen ohne Git-History-Rewrite.

Abnahme umfasst: `manage.py check --deploy` mit bewerteten Warnungen,
DB-/KnowledgeStore-Schreib-/Lesetest, authentifizierten Import, Chat und
Embedding, statische Assets und privaten Medienzugriff, CSRF/HTTPS-Login,
Neustart nach SSH-Abmeldung, automatische Crash-Recovery, gemessenen
RAM-/Speicherverbrauch sowie Backup-Restore. Lokaler HTTP-Erfolg oder
`systemctl active` allein ist keine vollstaendige Readiness.

SQLite-Backups bei freigegebenem Pilot konsistent ueber Backup-API oder bei
gestoppten Schreibern erstellen, nicht laufende WAL-Dateien einzeln kopieren.
PostgreSQL-Dumps auf Restore pruefen; den aktuell dokumentierten
U8-PostGIS-Dumpfehler beruecksichtigen. Quellen, Workspace, Artefakte und
private Medien mit sichern; eine DB-Sicherung allein reicht nicht.
Mindestens eine geschuetzte Kopie ausserhalb des Accounts vorsehen.

## Quellen

Offizielle Uberspace-8-Quellen, fuer diesen Entwurf am 02.11.2026 gelesen:

- [U7 zu U8: Arch Linux und systemd](https://u8manual.uberspace.de/first_u7/)
- [systemd-User-Services und Bootverhalten](https://u8manual.uberspace.de/services_systemd/)
- [Webbackends: U8-Syntax und Bind-Adresse](https://u8manual.uberspace.de/web_backends/)
- [DocumentRoot und Zugriffsgrenzen](https://u8manual.uberspace.de/web_documentroot/)
- [HTTP-Stack und HTTPS](https://u8manual.uberspace.de/background_http/)
- [Python und venv](https://u8manual.uberspace.de/lang_python/)
- [PostgreSQL, Extensions und Backups](https://u8manual.uberspace.de/database_postgresql/)
- [Account-Ressourcen](https://u8manual.uberspace.de/basics_resources/)

Projektbefund: `kistack`, `pyproject.toml`, `config/defaults/stack.yaml`,
`config/stages/prod.yaml`, `ki_knowledge/django_site/settings.py`,
`ki_knowledge/config_runtime.py`, `ki_knowledge/integrations/knowledge_store.py`
und `.gitignore`. Tool-Vertrag:
[stackctl-README im Workspace](../../../stackctl/README.md).
