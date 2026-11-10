---
project: ki-knowledge
scope: deployment
created: "2026-11-02 22"
updated: "2026-11-10 20"
update_reason: "Relocate shared documentation into doc/ and update references"
status: draft
agent_project: ki-knowledge
---

# Uberspace 8: Deployment-Umsetzung

## Status und Voraussetzungen

Ziel ist ein **rootloser Uberspace-8-Account**, kein eigener Ubuntu-VPS.
Bootstrap, Stage, Deployment und Runtime-Vorlage sind implementiert; der
generische **systemd-User-Adapter** liegt im Schwesterrepository stackctl.
Beide Repositories gemeinsam ausliefern. **Auf einem Zielhost wurde nichts
installiert, gestartet oder abgenommen.**

Die Bedienbefehle entsprechen [U7](UBERSPACE7_IMPLEMENTATION.md).
Gemeinsame Implementierung: `ki_knowledge/deployment/uberspace.py` und
Standardbibliothek-Bootstrap `deploy/uberspace_bootstrap.py`; Einstiegspunkte:
`deploy/uberspace7/` und `deploy/uberspace8/`.
Git/HTTPS, Projekt-venv, ki-core-Konfigurationsmerge und stackctl bleiben die
einzigen Installations-/Lifecycle-Vertraege. Keine duplizierten `.env`,
kein eigener Prozessmanager, kein Docker, nginx oder sudo auf Uberspace.
Andere Stages bleiben unveraendert.

Vor Installation bestaetigen:

- Versionierter Python-Interpreter ab 3.12, Git, `systemctl`, `journalctl`,
  `pg_dump` und Uberspace-CLI sind vorhanden. Die systemd-User-Instanz ist
  erreichbar und wird vom Anbieter beim Boot gestartet.
- Eigene Domain mit geprueftem DocumentRoot, freie Ports, Speicherquota und
  RAM-Budget. Django bindet `0.0.0.0`; die interne API bleibt auf Loopback.
- PostgreSQL-Datenbank mit **aktivem pgvector** und Nicht-Superuser-App-Rolle.
  Bootstrap legt weder Datenbank noch Erweiterung an.
- Ollama mit Embedding- und Chatmodell auf dem separaten Root-Server.
  Ein separat betreuter SSH-Tunnel lauscht auf `127.0.0.1:11434`; Schluessel,
  Host-Key-Pruefung und automatische Wiederverbindung vorher einrichten.

### PostgreSQL und pgvector bleiben ein Host-Gate

U8 stellt PostgreSQL mit Accountrolle und privater `~/.pgpass` bereit.
Zusaetzliche Datenbanken muessen mit dem Accountnamen beginnen.
Das gelesene Handbuch sichert **pgvector nicht zu**; die Rolle kann nicht
beliebige native Extensions selbst installieren.

In der tatsaechlichen App-Datenbank lesend pruefen:

```sql
SELECT current_database(), current_user, version();
SELECT name, default_version, installed_version
FROM pg_available_extensions WHERE name = 'vector';
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT rolsuper FROM pg_roles WHERE rolname = current_user;
SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector;
```

Der Distanzvergleich muss `0` ergeben. Fehlende Bereitstellung/Aktivierung
mit dem Anbieter klaeren oder **explizit externes PostgreSQL mit pgvector**
konfigurieren. DSN und externe Stack-Host-/Portwerte muessen uebereinstimmen.
Es gibt keinen stillen SQLite-Fallback; dieser Deploymentpfad setzt PostgreSQL
fuer Django und KnowledgeStore voraus. Keine Datenmigration durch DSN-Wechsel.

## Erstinstallation

Im HTTPS-Checkout, mit vertrauenswuerdigem aktuellem stackctl-Checkout daneben:

```bash
python3.12 deploy/uberspace8/bootstrap.py --stackctl-source ../stackctl
mkdir -p config/runtime
```

Bootstrap erstellt nur eine fehlende `.venv`, installiert stackctl editierbar,
ruft dessen Sibling-Installation mit dem Extra `uberspace8` auf und prueft
Abhaengigkeiten. Eine unvollstaendige oder zu alte vorhandene venv wird
nicht ueberschrieben. **Keine Hostdienste, Datenbanken oder Webbackends
werden dabei eingerichtet.**

`config/runtime/runtime.yaml` anhand von
`deploy/uberspace8/runtime.example.yaml` anlegen oder die benoetigten Werte
in die bestehende Datei **zusammenfuehren, nicht ueberschreiben**:
Account, Domain, Daten-/Backup-/Static-/Medienpfade, DSN, Ports und
tatsaechlich installierten Chatmodellnamen ersetzen.
Bei Anbieter-PostgreSQL den Hostnamen an den vorhandenen `.pgpass`-Eintrag
anpassen; `localhost` und `127.0.0.1` sind dort nicht automatisch austauschbar.

Secrets bleiben in privater `creds.yaml` bzw. vorhandener `.pgpass`, Modus
`0600`; Vorlage: `deploy/uberspace8/creds.example.yaml`. Einen zufaelligen Django-Schluessel von mindestens 50 Zeichen unter
`apps.ki_knowledge.django.secret_key` eintragen. Keine Zugangsdaten in Units,
Beispiele, Shellhistorie oder Git uebernehmen.

Hostlayout:

```text
~/ki/src/ki-knowledge/                         Checkout und .venv
~/ki/src/stackctl/                             Tool-Checkout
~/ki/src/<siblings>/                           deklarierte Geschwister
~/ki/data/ki-knowledge/                        private Daten und Medien
~/ki/backups/ki-knowledge/                     private Sicherungen
~/.config/systemd/user/                        verwaltete User-Units
/var/www/virtual/<account>/<domain>/static/     oeffentliche Assets
```

DocumentRoot muss bereits existieren und zur Domain passen. U8 legt Domains
zunaechst als Symlinks auf `html` an: vor Verwendung pruefen, ob mehrere
Domains denselben Inhalt teilen. Keine Symlinks auf private Home-Daten
veroeffentlichen. `static_root` muss exakt `<document_root>/static` sein;
`media_root` bleibt im privaten Datenroot. Static-Dateien erhalten `0644`,
Verzeichnisse `0755`; Backups bleiben privat.

Die Stage setzt sichere Cookies, HTTPS-Redirect und eine Stunde HSTS.
Den `X-Forwarded-Proto`-Vertrag des U8-Frontends **vor** Aktivierung von
`secure_proxy_ssl_header` bestaetigen. Explizite Hosts, HTTPS-CSRF-Origin und
oeffentliche Wagtail-Admin-URL sind Pflicht.
Prozessgebundene Konfigurations-Overrides werden beim Deployment abgelehnt,
damit User-Units nach einem Neustart denselben dateibasierten Stand verwenden.

```bash
.venv/bin/python deploy/uberspace8/deploy.py check
.venv/bin/python deploy/uberspace8/deploy.py apply
```

`check` prueft Settings, Hosttools, User-Manager, PostgreSQL/pgvector,
App-Rolle und benoetigte Ollama-Modelle. Django-Deploywarnungen werden
ausgegeben und blockiert, ausser bewusst nicht erzwungenem HSTS fuer weitere
Subdomains/Preloading (`security.W005`/`security.W021`).

`apply` stoppt nur Django/API, sichert Daten, migriert, initialisiert das
KnowledgeStore-Schema, sammelt Assets und startet ueber stackctl.
Es prueft danach HTTP mit Domain und verifiziertem HTTPS-Proxyheader lokal.
Externer Login, CSRF, Import und Chat/Embedding sind Teil der Hostabnahme,
nicht durch einen offenen TCP-Port bewiesen.

## systemd-User-Lifecycle und Webrouting

```bash
KI_STAGE=prod-uberspace8 ./kistack status
KI_STAGE=prod-uberspace8 ./kistack logs django
KI_STAGE=prod-uberspace8 ./kistack restart django api
KI_STAGE=prod-uberspace8 .venv/bin/python manage.py createsuperuser
```

Alternativ die Stage in `config/stages/.active_stage` hinterlegen.
`kistack` bevorzugt die Projekt-venv. stackctl rendert ausschliesslich
eigene Units mit Projekt-cwd, venv-Interpreter und expliziter Stage.
Systemd startet die Dienste im Vordergrund, fuehrt keine Migration bei
Crash-Recovery aus und protokolliert ins Journal. `WantedBy=default.target`
erlaubt den Bootstart; User-Manager/Abmeldung auf dem Host abnehmen.
Ein explizites `stop` deaktiviert auch den Bootstart; `start` aktiviert ihn
wieder. Nach fehlgeschlagenem Deployment bleiben die Schreiber damit auch
nach einem Hostneustart gestoppt.
Externe PostgreSQL-/Ollama-Abhaengigkeiten werden nur geprueft, nicht verwaltet.
Keine systemweiten Units, kein globaler Neustart fremder Dienste.

Domain-Routing wird **separat freigegeben**:

```bash
# Bestand anzeigen; ohne Bestaetigung bewusst kein Schreibzugriff:
.venv/bin/python deploy/uberspace8/deploy.py web
# Genau diese Domain und ihre zwei Pfade zum Ersetzen freigeben:
.venv/bin/python deploy/uberspace8/deploy.py web --confirm-domain DEINE.DOMAIN
```

Nach exakter Bestaetigung verwendet das Skript die U8-Syntax
`uberspace web backend add DOMAIN/ port PORT --force` und
`add DOMAIN/static static --force`. `--force` gilt nur fuer diese beiden
freigegebenen Pfade, nie fuer das globale Standardbackend.
Bestehende Zuordnungen vorher dokumentieren. Private Medien, API und
Datenbank erhalten **kein** oeffentliches Backend.

## Backups, Updates und Wiederherstellung

```bash
.venv/bin/python deploy/uberspace8/deploy.py backup
.venv/bin/python deploy/uberspace8/deploy.py update
```

`backup` stoppt App-Schreiber und laesst sie danach absichtlich gestoppt.
`update` verlangt saubere Projekt-/Tool-/Sibling-Checkouts mit Upstream,
sperrt parallele Deployments, stoppt Django/API, sichert und zieht jedes Repo
per `git pull --ff-only`. Bei geaenderten Dependency-Manifesten erfolgt
erneute Installation, immer `pip check`; anschliessend laeuft der aktualisierte
Deploymentcode unter derselben vererbten Sperre.
U7 und U8 teilen je Checkout `var/uberspace.lock`; laufende alte
U7-Deployments vor Umstellung abschliessen.

Kein Stash/Reset, kein automatischer Rollback und keine atomare
Multi-Repo-Transaktion: Fehler koennen bereits aktualisierte Checkouts und
gestoppte App-Schreiber hinterlassen. Externe Dienste bleiben unberuehrt.
Import-/Cron-Schreiber vorab eigenstaendig pausieren.

Private Sicherungen enthalten Custom-Format-PostgreSQL-Dump, Datenarchiv,
Hostkonfiguration und Revisions-/Paketmanifest. Symlinks werden nicht verfolgt:
externe Quellen separat sichern und geschuetzte off-host Kopie vorsehen.

### Anbieter-PostGIS-Dumpfehler

Das aktuelle U8-Handbuch beschreibt einen Fehler beim Dump automatisch
bereitgestellter PostGIS-Objekte. Standardmaessig wird **nichts ausgeschlossen**.
Nur bei bestaetigtem Anbieterfall und ohne eigene Daten in diesen Schemas
`apps.ki_knowledge.uberspace8.exclude_provider_postgis: true` setzen.
Das Skript prueft dann `pg_dump` auf `--exclude-extension`-Unterstuetzung
und verwendet die dokumentierten Ausschluesse fuer `public.spatial_ref_sys`,
`tiger`, `tiger_data`, `topology` sowie `postgis`, `postgis_topology`,
`postgis_tiger_geocoder` und `fuzzystrmatch`. **pgvector bleibt enthalten.**
Alle Ausschluesse stehen im Backupmanifest.

Solche Dumps benoetigen die ausgeschlossenen Anbieterobjekte bereits im
Restore-Ziel. Nicht ungeprueft auf externe Datenbanken uebertragen.
Bei externem PostgreSQL oder eigenen Daten in ausgeschlossenen Schemas
diesen Schalter nicht aktivieren; Backupstrategie separat klaeren.

Restore zuerst in separater Datenbank und separatem Datenroot erproben:
passende Extensions administrativ bereitstellen, Dump per `pg_restore`
einspielen, Datenarchiv und private Konfiguration zuordnen und kompatible
Revisionen aus dem Manifest verwenden. Nicht ueber Live-Daten restaurieren.

Hostabnahme: DB-/KnowledgeStore-Schreib-/Lesetest, HTTPS-Login/CSRF, Import,
Chat/Embedding, Assets/Medienrechte, SSH-Abmeldung, Boot-/Crash-Recovery,
Ressourcenverbrauch und Restore. Erst danach unbeaufsichtigte Updates
oder einen opt-in Timer freigeben.

## Einstiege und Quellen

[Deployment](README.md), [Config-Merge](CONFIG_MERGE_REFERENCE.md),
[Dokumentationsbaum](../README.md),
[Server-Management im Workspace](../../../../dev_doc/doc/server-mngm/SERVER_MANAGEMENT_README.md).

Offizielle Dokumentation, fuer die Umsetzung am 03.11.2026 erneut geprueft:

- [systemd-User-Services und Bootverhalten](https://u8manual.uberspace.de/services_systemd/)
- [U8-Webbackends und Bind-Adresse](https://u8manual.uberspace.de/web_backends/)
- [DocumentRoot und Dateirechte](https://u8manual.uberspace.de/web_documentroot/)
- [PostgreSQL, Extensions und PostGIS-Dump-Workaround](https://u8manual.uberspace.de/database_postgresql/)
- [Python](https://u8manual.uberspace.de/lang_python/)
- [HTTP-Stack und HTTPS](https://u8manual.uberspace.de/background_http/)
- [Ressourcen](https://u8manual.uberspace.de/basics_resources/)
