---
project: ki-knowledge
scope: deployment
created: "2026-11-03 01"
updated: "2026-11-10 20"
update_reason: "Relocate shared documentation into doc/ and update references"
status: draft
agent_project: ki-knowledge
---

# Uberspace 7: Deployment-Umsetzung

## Status und Einordnung

Ziel ist ein bestehender **Uberspace-7-Account ohne Root-Zugriff**.
Dieser Plan beruecksichtigt bereits manuell eingerichtete Anwendungen:
Bestand aufnehmen und integrieren, nicht neu initialisieren oder fremde
Dienste uebernehmen. Stage, Bootstrap und Deploymentskript sind im Repository
implementiert; der generische supervisord-Adapter liegt im Schwesterprojekt
stackctl. **Auf Uberspace noch nicht installiert oder abgenommen.**

U7 und U8 verwenden denselben Deploymentkern in
`ki_knowledge/deployment/uberspace.py` und den Standardbibliothek-Bootstrap in
`deploy/uberspace_bootstrap.py`; die versionsbezogenen Einstiegspunkte bleiben
erhalten. Beide Versionen sperren denselben Checkout ueber `var/uberspace.lock`.
Vor Umstellung laufende alte U7-Deployments mit bisheriger Sperrdatei abschliessen.

## Bedienbarer Repository-Stand

Voraussetzungen: vorhandener PostgreSQL-Cluster mit eigener App-Datenbank,
administrativ aktiviertes `vector`, separate App-Rolle ohne Superuserrechte,
U7-DocumentRoot fuer eine freigegebene Domain und eine separat betreute
SSH-Tunnelverbindung zu Ollama auf dem dedizierten Root-Server.
Der Tunnel lauscht auf `127.0.0.1:11434`; der entfernte Ollama-Dienst bleibt
ebenfalls privat. Schluessel/Host-Key-Pruefung und automatische
Wiederverbindung sind Voraussetzung, nicht Aufgabe des App-Deployments.

Die fuer diese Installation verwendeten Revisionen von **ki-knowledge und
stackctl gemeinsam** ausliefern. Ein aelteres stackctl ohne Ziel
`supervisord` reicht nicht. Keine Dependency wird aus einem willkuerlichen
gleichnamigen PyPI-Paket als Ersatz fuer das Tool-Checkout bezogen.

```bash
# Im HTTPS-Checkout von ki-knowledge; vertrauenswuerdiges Tool-Checkout daneben.
python3.12 deploy/uberspace7/bootstrap.py --stackctl-source ../stackctl
mkdir -p config/runtime
```

Dient noch keine Runtime-Datei diesem Checkout, `config/runtime/runtime.yaml`
anhand von `deploy/uberspace7/runtime.example.yaml` anlegen. Bei vorhandener
Datei die benoetigten Eintraege zusammenfuehren, **nicht ueberschreiben**.
Alle Beispielwerte ersetzen, insbesondere Account, Domain,
Datenpfade, App-Rolle/-Datenbank und den auf dem Root-Server installierten
Chatmodellnamen. Zugangsdaten gehoeren nach `creds.yaml` bzw. in die vorhandene
private `.pgpass`. Vorlage: `deploy/uberspace7/creds.example.yaml` nach
`creds.yaml` im Checkout kopieren. Django-Schluessel als zufaelligen, mindestens 50 Zeichen
langen Wert lokal erzeugen und unter `apps.ki_knowledge.django.secret_key`
in `creds.yaml` eintragen. `chmod 600 creds.yaml ~/.pgpass` nur auf die
tatsaechlich verwendeten Dateien anwenden.

Den U7-Proxyvertrag vor Uebernahme des Beispielheaders bestaetigen.
Die Stage setzt sichere Cookies, HTTPS-Redirect und zunaechst eine Stunde HSTS.
Die Deploypruefung gibt Warnungen aus und blockiert sie, mit zwei bewusst
akzeptierten Ausnahmen: `security.W005`/`security.W021` fuer nicht aktiviertes
HSTS auf weiteren Subdomains bzw. Browser-Preloading. Beides wird nicht
ungefragt fuer andere Dienste erzwungen.
`static_root` muss exakt `<document_root>/static` sein. `media_root` bleibt
im privaten Datenroot; kein oeffentliches Medienbackend wird angelegt.
Oeffentliche Assets erhalten getrennt davon Apache-lesbare Rechte.

```bash
.venv/bin/python deploy/uberspace7/deploy.py check
.venv/bin/python deploy/uberspace7/deploy.py apply
# Zeigt Bestand und bricht ohne Bestaetigung bewusst ab:
.venv/bin/python deploy/uberspace7/deploy.py web
# Erst nach Freigabe der zwei domainbezogenen Backend-Zuordnungen:
.venv/bin/python deploy/uberspace7/deploy.py web --confirm-domain DEINE.DOMAIN

KI_STAGE=prod-uberspace7 ./kistack status
KI_STAGE=prod-uberspace7 ./kistack logs django
KI_STAGE=prod-uberspace7 .venv/bin/python manage.py createsuperuser
```

`check` prueft effektive Django-Settings, externe PostgreSQL-/pgvector-
Verbindung mit App-Rolle und die benoetigten Ollama-Modelle.
Prozessgebundene `KI_CFG_*`-/`DJANGO_*`-Overrides werden beim Deployment
abgelehnt: dieselbe Konfiguration muss auch nach supervisord-Neustart aus
Dateien gelten. `apply` stoppt nur Django/API, erstellt eine Sicherung,
prueft Django-Deploywarnungen, migriert, initialisiert den KnowledgeStore,
sammelt Assets und startet ueber stackctl. Es initialisiert und stoppt
**keinen** PostgreSQL-Cluster und installiert **keine** Ollama-Modelle.
Die lokale HTTP-Pruefung verwendet Domain und geprueften HTTPS-Proxyheader;
externer HTTPS-Login und fachlicher Schreib-/Lesetest folgen auf dem Zielhost.

Fuer spaetere Lifecycle-Aufrufe entweder `KI_STAGE=prod-uberspace7` setzen
oder `prod-uberspace7` in `config/stages/.active_stage` eintragen.
`kistack` verwendet jetzt vorrangig `.venv/bin/python -m stackctl`; der globale
Aufruf bleibt nur fuer Checkouts ohne Projekt-venv kompatibel erhalten.

### Updates und Sicherungen

```bash
# Nach freigegebenem git push; zieht die aktuell eingerichteten Upstreams nach.
.venv/bin/python deploy/uberspace7/deploy.py update
# Nur Sicherung; Django/API bleiben danach absichtlich gestoppt:
.venv/bin/python deploy/uberspace7/deploy.py backup
```

Update erfordert saubere Git-Checkouts mit Upstream fuer Projekt, stackctl
und deklarierte Siblings. Es sperrt parallele Deployments, stoppt App-Schreiber,
sichert Daten und zieht jedes Repo per `git pull --ff-only` nach.
Bei geaenderten `pyproject.toml` werden die Projekt-/Sibling-Abhaengigkeiten
erneut installiert; bei jedem Update folgt `pip check`. Anschliessend wird
der neue Deploymentcode unter derselben Sperre ausgefuehrt.
Die Repo-Updates sind **keine atomare Multi-Repo-Transaktion**: bei Fehlern
koennen einzelne Checkouts bereits aktualisiert sein. Kein automatischer
Rollback und kein impliziter Wiederanlauf nach Fehlern.

Sicherungen im privaten `backup_root` enthalten PostgreSQL-Dump, Datenarchiv,
private Hostkonfiguration und Revisions-/Paketmanifest. Verzeichnisrechte:
`0700`, Dateien privat. Symlinks im Datenbaum werden nicht verfolgt:
externe Quellen oder weitere ausserhalb liegende Speicher separat sichern.
Zusaetzliche Import-/Cron-Schreiber vor Deployment eigenstaendig pausieren;
andere Anwendungen einer geteilten Instanz werden nicht angehalten.

Restore zuerst in einer separaten Datenbank und einem separaten Datenroot
erproben: pgvector administrativ bereitstellen, Dump mit `pg_restore`
unter passenden Rechten wiederherstellen, Datenarchiv und private Konfiguration
zuordnen, kompatible Revisionsstaende laut Manifest bereitstellen.
Nicht ungeprueft ueber Live-Daten restaurieren. Fuer unbeaufsichtigten
Produktivbetrieb fehlen bis zur Hostabnahme insbesondere Restore-Nachweis,
off-host Backupkopie und kontrollierte externe Readiness.

Einstiege: [Deployment](README.md), [Config-Merge](CONFIG_MERGE_REFERENCE.md),
[Dokumentationsbaum](../README.md). Der
[U8-Leitfaden](UBERSPACE8_IMPLEMENTATION.md) beschreibt dieselbe Deployment-Linie,
aber einen anderen Plattformadapter. Gemeinsame Grundlagen:
[Server-Management](../../../../dev_doc/doc/server-mngm/SERVER_MANAGEMENT_README.md).
Workspace-Links setzen benachbarte Repositories voraus.

## 1. Was fuer U7 anders ist

| Bereich | Uberspace 7 | Abgrenzung zu U8 |
|---|---|---|
| Basis | CentOS 7 mit Anbieter-Sicherheitspflege; aktuelle Paket-/Wheel-Kompatibilitaet separat pruefen. | Nicht Arch Linux. |
| Prozesse | Vorhandenes supervisord; Service-Dateien in `~/etc/services.d/`, Bedienung per `supervisorctl`. | Keine systemd-User-Units. |
| Web | Anbieter-HTTPS-/Proxyinfrastruktur, Static-Dateien ueber Apache im DocumentRoot. | U7 verwendet `web backend set`, nicht U8 `add … port`. |
| Bind-Adresse | Webdienst auf `0.0.0.0` oder `::`, Port 1024–65535. | Loopback reicht fuer das oeffentliche Webbackend nicht. |
| PostgreSQL | Anbieter stellt Binaries; eigener Cluster laeuft im Benutzerkonto. Vorhandene Instanz bevorzugt pruefen. | Kein automatisch bereitgestellter U8-Datenbankdienst voraussetzen. |
| Python | Versioniertes Binary verwenden, vorgeschlagen Python 3.12 nach Kompatibilitaetspruefung. | Weder `python` noch `python3` ungeprueft verwenden. |
| Budget | Speicherquota und vorhandenen Ressourcenverbrauch ermitteln; standardmaessig 10 GB Speicher laut U7-Handbuch. | U8-RAM-Limits nicht als U7-Zusage uebernehmen. |

Die Versionslisten im U7-Handbuch enthalten auch alte Beispiele. Massgeblich
sind die auf dem konkreten Account verfuegbaren und noch gepflegten Versionen.
Eine PostgreSQL-Majorversion niemals als Nebeneffekt des App-Deployments
wechseln; das ist ein eigener Upgradevorgang mit Backup/Restore bzw. pg_upgrade.

## 2. Zielarchitektur und Bestandsschutz

```text
Browser -- HTTPS --> Uberspace-Webfrontend
                       | /static -> Apache / DocumentRoot
                       | /       -> Django WSGI auf 0.0.0.0:<web-port>
                                         |
                              Knowledge-API auf 127.0.0.1:<api-port>
                                         |
                          bestehende oder eigene PostgreSQL-Instanz

stackctl -> supervisord-Adapter -> ausschliesslich verwaltete Programmnamen
ki-core  -> normaler Config-Merge -> Stage prod-uberspace7
```

Git-Transport per HTTPS, projektbezogene `.venv`, deklarierte
Geschwister-Repositories und stackctl bleiben die Einstiege. Kein eigener
Prozessmanager, kein zweiter PID-Bestand, keine duplizierten `.env`-Dateien.
Bootstrap und `kistack` verwenden den projektbezogenen stackctl-Aufruf.

Die Stage verwendet Gunicorn fuer WSGI, zunaechst einen Worker mit zwei
Threads, und Uvicorn ohne Reload fuer die interne API. Gunicorn ist im
Extra `uberspace7` deklariert. Keine Docker-Dienste, eigener nginx oder
`runserver --insecure` fuer diesen Zielaufbau.

PostgreSQL nur dann von stackctl verwalten lassen, wenn es eine eigens diesem
Projekt zugeordnete Instanz ist. Eine vorhandene, von mehreren Anwendungen
genutzte Instanz ist eine **externe Abhaengigkeit**: App-Stop/Update darf sie
nicht stoppen. Bestehende `.pgpass`, Clusterverzeichnisse, Datenbanken,
Service-Dateien und Webbackends nicht ueberschreiben.

## 3. pgvector: technische Bedeutung und konkrete Pruefung

**pgvector ist eine PostgreSQL-Erweiterung, kein KI-Modell und kein eigener
Server.** Sie ergaenzt PostgreSQL um Vektordatentypen, Distanzoperatoren und
optionale Suchindizes. Ein Embedding-Modell wandelt Text in eine Zahlenliste
um; pgvector speichert diese Liste und vergleicht sie mit anderen Listen.

```text
Textblock -> Embedding-Modell -> Zahlenvektor -> PostgreSQL + pgvector
Suchfrage -> dasselbe Modell -> Suchvektor   -> aehnliche Textbloecke
```

Aehnliche Bedeutungen sollen im Vektorraum nahe beieinanderliegen.
Das ist modellabhaengige semantische Aehnlichkeit, keine Wahrheitspruefung.
Dokument- und Suchvektoren muessen aus einem kompatiblen Modell mit derselben
Dimension und passender Vorverarbeitung stammen.

In ki-knowledge legt `KnowledgeStore._init_schema()` unter PostgreSQL eine
Spalte vom Typ `vector` an und aktiviert `vector` per
`CREATE EXTENSION IF NOT EXISTS vector`. `similar_blocks()` verwendet
`<=>` fuer Cosinusdistanz und berechnet `1 - Distanz` als Aehnlichkeit.
Diese Zahl ist keine Wahrscheinlichkeit. Die hier betrachtete Suchmethode
funktioniert ohne eigens angelegten HNSW-/IVFFlat-Index; solche Indizes waeren
eine spaetere Optimierung mit eigenem Speicher-/Qualitaetsbudget.

**Zwei getrennte Voraussetzungen:**

1. Die Extension-Dateien samt nativer Bibliothek muessen zur PostgreSQL-
   Majorversion passend auf dem **Datenbankserver** installiert sein.
   `pip install` im Django-venv erledigt das nicht.
2. Die Erweiterung muss in der verwendeten Datenbank aktiviert werden.
   Dafuer sind normalerweise PostgreSQL-Superuserrechte erforderlich.
   Ein PostgreSQL-Superuser ist nicht dasselbe wie Linux-root.

Beim U7-Cluster ist der initiale Clusteradministrator laut Anbieteranleitung
typischerweise der eigene Account. **Voraussetzung 1 ist fuer U7 grundsaetzlich
dokumentiert:** Das Changelog zu Uberspace 7.15.3 vom 19.06.2023 nennt
pgvector fuer PostgreSQL 12–15. Ein eigener Extension-Build ist damit nicht
der vorgesehene Installationsweg. Die lesende Pruefung unten bestaetigt nur
noch den konkreten Serverstand und die Aktivierung in der Zieldatenbank.
Die installierte pgvector-Version mit erfassen; aus der damaligen
Bereitstellung folgt keine Zusage ueber heutige Versionsstaende oder alle
neueren Indexfunktionen. Falls die Extension auf dem Account wider Erwarten
fehlt, mit Verweis auf das Changelog den Uberspace-Support kontaktieren.

### Lesende Pruefung in der tatsaechlichen Zieldatenbank

Mit der vorhandenen Verbindung per `psql` anmelden, ohne Passwort in
Kommandozeile, Shellhistorie oder Ausgaben zu kopieren. Dann:

```sql
SELECT current_database(), current_user, version();
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'vector';
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
SELECT rolname, rolsuper
FROM pg_roles
WHERE rolname = current_user;
```

Keine Zeile in `pg_available_extensions`: fuer diese Serverinstallation
nicht angeboten; nicht nur ein fehlendes Python-Paket.
Zeile mit `installed_version IS NULL`: vorhanden, aber in dieser Datenbank
noch nicht aktiviert. Ein Eintrag in `pg_extension` bestaetigt die Aktivierung.
Die Abfragen belegen noch nicht die Schreib-/Schemarechte der App-Rolle.

### Bewusste Aktivierung durch den DB-Administrator

Erst nach Freigabe und in der richtigen Datenbank:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector AS cosine_distance;
```

Der Vergleich muss `0` ergeben. Anschliessend mit der separaten App-Rolle
den echten KnowledgeStore-Schreib-/Lesetest durchfuehren.
Die Webanwendung nicht allein fuer Extension-Installation zum Superuser
machen; Erweiterung administrativ vorab aktivieren.

Fehlt pgvector, funktioniert der derzeitige PostgreSQL-KnowledgeStore nicht
einfach ohne Vektorsuche: die Abhaengigkeit entsteht bereits beim Schemaaufbau.
Moegliche bewusste Alternativen sind externes PostgreSQL mit pgvector oder
ein SQLite-Pilot. SQLite speichert hier Vektoren als JSON und vergleicht sie
in Python; fuer kleine Bestaende brauchbar, aber kein gleichwertiger
Skalierungsersatz. Kein stiller Wechsel und keine implizite Datenmigration.

## 4. Implementierte Artefakte und Verantwortlichkeiten

| Ort | Aufgabe |
|---|---|
| `stackctl` | Generischer supervisord-Adapter: aus derselben Service-Spec Programmkonstruktion, Start/Stop/Restart, Status und Logs; keine Knowledge-Logik. |
| `config/stages/prod-uberspace7.yaml` | Debug aus, WSGI, API ohne Reload, keine Compose-Dienste oder geerbten Model-Pull-Hooks; externe Abhaengigkeiten explizit. |
| `deploy/uberspace7/bootstrap.py` | Explizite Interpreter-/Toolpruefung und venv-/Sibling-Installation; keine Hostdienste oder Datenbankinitialisierung. |
| `deploy/uberspace7/deploy.py check` | Effektive Konfiguration, Hostvoraussetzungen, App-Datenbankrolle, pgvector und Ollama-Modelle pruefen. |
| `deploy/uberspace7/deploy.py web` | Ausschliesslich genehmigte Domain-/Pfad-Zuordnungen ueber die U7-CLI konfigurieren. |
| `deploy/uberspace7/deploy.py update` | Gesperrter Git-/Backup-/Migrations-/Asset-/Restart-Ablauf ueber stackctl. |
| Django-Settings, Schema, `pyproject.toml` | WSGI-Dependency, konfigurierbare Static-/Medienpfade, sichere Cookies, CSRF und gepruefter Proxyvertrag. |
| Tests | Plattformadapter in stackctl; Projekt-Spec, Bootstrap und Update-Fehlerpfade in ki-knowledge. |

Der Bedienabschnitt oben beschreibt die implementierten Einstiegspunkte;
die folgende Architektur bleibt die Grundlage fuer die Hostabnahme.
Python-Skripte mit Argumentlisten, Timeouts und klaren Fehlermeldungen;
keine langen Python-Bloecke in Shellskripten.

Supervisord startet die eigentlichen Dienste im Vordergrund, nicht nochmals
`stackctl start` als zweiten Hintergrundmanager. Absolute venv-Kommandos,
Projektroot als `directory`, explizite Stage, begrenzte Startversuche,
geeignete Stop-Signale/Timeouts und Logrotation vorsehen. Keine Migration bei
jeder automatischen Crash-Recovery. `reread`/`update` koennen auch fremde
ausstehende Konfigaenderungen betreffen: Bestand pruefen und Anwendung auf
benannte Projektgruppen begrenzen; kein globales `restart all`.

## 5. Hostlayout, Konfiguration und Web

Checkouts in `~/ki/src/`, App-Daten in `~/ki/data/ki-knowledge/`,
Backups in `~/ki/backups/ki-knowledge/`; vorhandene PostgreSQL-Clusterpfade
beibehalten. Service-Dateien liegen unter `~/etc/services.d/`, Logs unter
dem dafuer vorgesehenen privaten Logpfad. Nur oeffentliche Static-Dateien
kommen in den DocumentRoot unter `/var/www/virtual/<account>/`.

Hostwerte in `config/runtime/runtime.yaml`, Secrets in `creds.yaml` bzw.
passender privater `.pgpass` mit `0600`; keine fremden Eintraege ersetzen.
Config-Merge bleibt unveraendert. Aufgeloeste Hosts, DSN, Datenroot,
Provider-/API-/Wagtail-URLs und Stage pruefen, ohne Secrets auszugeben.

Embeddings weiterhin ueber externes, abgesichertes Ollama mit
`nomic-embed-text`; Chat ueber den vorhandenen Provideradapter.
Kein lokales Modell allein deshalb starten, weil die Standard-Spec es enthaelt.
HTTPS-Erkennung und sichere Cookies/CSRF sind konfigurierbar; vertrauenswuerdige
Proxyheader vor Konfiguration nachweisen. Private Medien nicht durch ein
pauschales oeffentliches `/media`-Backend exponieren.

U7-Routingbeispiel, erst nach Bestandspruefung und laufendem WSGI-Dienst,
mit konkret ersetzten Platzhaltern:

```bash
uberspace web backend list
uberspace web backend set <domain>/ --http --port <web-port>
uberspace web backend set <domain>/static --apache
uberspace web backend list
```

`set` kann bestehende Zuordnungen ersetzen: vorher dokumentieren und
explizit freigeben. `collectstatic` muss in den zu dieser Domain passenden
DocumentRoot schreiben; Quellcode, `.git`, Daten und Secrets bleiben privat.
Interne API und PostgreSQL erhalten kein oeffentliches Webbackend.

## 6. Umsetzung, Updates und Abnahme

1. **Bestehenden Account aufnehmen:** Dienste, Ports, Datenbankversion/-pfad,
   Rollen, Backends, Python, Ressourcen und Backups. Zuerst pgvector pruefen;
   vorhandene Anwendungen bleiben unberuehrt.
2. **Lifecycle-Vertrag ausliefern:** Implementierten stackctl-/venv-Einstieg,
   supervisord-Adapter und U7-Stage gemeinsam bereitstellen. Bestehende
   geteilte PostgreSQL-Instanz als extern behandeln.
3. **Pilot installieren:** Abhaengigkeiten, sichere Settings, Migration,
   KnowledgeStore-Test und Assets; Dienste starten, Readiness nachweisen,
   erst dann genehmigte Domain routen.
4. **Updatepfad:** Saubere, freigegebene Branches und Sibling-Revisionen per
   Git/HTTPS und `git pull --ff-only`; Schreibzugriffe geordnet pausieren,
   konsistente Sicherung vor Migration, Installation bei Bedarf, Assets,
   Neustart und fachliche Readiness. Keine fremden Dienste stoppen.
5. **Restore und Automatik:** Daten und Coderevisionen zusammen wiederherstellen
   koennen; erst danach optional Cron oder kontrollierter SSH-Deployaufruf.
   Nicht unkontrolliert jeden Push direkt auf Produktion anwenden.

Updates sperren, Fehler mit ungleich null und tatsaechlichem Zustand melden;
kein automatisches Stash/Reset/Branchwechsel und keine Rueckmigration auf
Verdacht. Dumps, Quellen, Workspace, Artefakte und private Medien sichern,
Revisions-/Paketmanifest mitfuehren und geschuetzte externe Backupkopie anlegen.
Physische PostgreSQL-Datenverzeichnisse nicht bei laufendem Server kopieren.
Bei SQLite Backup-API oder gestoppte Schreiber verwenden.

Abnahme: Django-Deploycheck, DB und KnowledgeStore mit App-Rolle, Login/CSRF,
Import, Chat/Embedding, Assets/Medienrechte, SSH-Abmeldung und Dienst-Recovery,
Ressourcenverbrauch und Restore. Ein `RUNNING` in supervisord oder
erfolgreicher Django-Login allein bestaetigt noch keinen KnowledgeStore.

## 7. Eignung: U7 oder U8?

**Fuer den ersten ki-knowledge-Betrieb auf dem vorhandenen, vertrauten Account
ist U7 die pragmatische Empfehlung.** pgvector ist dokumentiert verfuegbar,
supervisord bekannt und ein Plattformwechsel nicht Voraussetzung fuer den
fachlichen Pilot. Fuer eine neue, langfristig angelegte Installation ist U8
die modernere Basis, sobald pgvector dort bestaetigt und aktivierbar ist.

| Kriterium | U7 | U8 |
|---|---|---|
| Sofortiger Einstieg | Bestehende Einrichtung und Betriebserfahrung nutzbar. | Zusaetzliche Plattformumstellung und eigener Adapter. |
| pgvector | Fuer PostgreSQL 12–15 im Changelog bestaetigt; Zieldatenbank aktivieren. | Im gelesenen PostgreSQL-Handbuch nicht zugesichert; keine Behauptung, dass es fehlt. |
| Datenbankbetrieb | Eigener Cluster bietet administrative Kontrolle, erfordert aber eigene Pflege und Backuporganisation. | Anbieterbetrieb und taegliche PostgreSQL-Backups reduzieren Eigenbetrieb; weniger administrative Freiheit. |
| Python-/Native-Pakete | Aeltere Systembasis kann moderne Wheels oder native Abhaengigkeiten erschweren, trotz aktueller Python-Binaries. | Aktuelle Systembibliotheken/Compiler erleichtern tendenziell moderne Dependencies; Rolling Updates verlangen Regressionstests. |
| Lifecycle | Bewaehrtes supervisord, stackctl-Adapter implementiert; Hostabnahme ausstehend. | systemd-User-Services und Journal; stackctl-Adapter implementiert, Hostabnahme ausstehend. |
| Perspektive | CentOS-7-Basis wird laut Anbieter weiter sicherheitsgepflegt; nicht mit ungepatchtem Standard-CentOS gleichsetzen. | Aktive Weiterentwicklung auf Arch Linux; Anbieter bezeichnet U8 auf der Vergleichsseite noch als Beta hinsichtlich Featurevollstaendigkeit. |

Es gibt keinen belegten pauschalen Geschwindigkeitsvorteil einer Plattform
fuer diese Anwendung. Datenmenge, Datenbank-/Indexkonfiguration, parallele
Imports und Providerlatenz sind entscheidender. Beide Varianten sind
Shared Hosting und kein geeigneter Ausgangspunkt fuer einen unbesehen
mitgestarteten lokalen LLM-Stack. Den Embedding-/Chatbetrieb getrennt planen.

Ein spaeterer U7-zu-U8-Wechsel bleibt moeglich: App-/Configvertrag gleich
halten, Plattformadapter austauschen und PostgreSQL logisch per Dump/Restore
migrieren. Extension-Versionen und Restore vorher auf dem Ziel pruefen;
Clusterverzeichnisse verschiedener PostgreSQL-Majorversionen nicht kopieren.

## Quellen

Offizielle Dokumentation, am 03.11.2026 fuer diesen Entwurf gelesen:

- [U7 supervisord](https://manual.uberspace.de/daemons-supervisord/)
- [U7 PostgreSQL-Binaries](https://manual.uberspace.de/database-postgresql/)
- [U7 PostgreSQL-Cluster und Erweiterungen](https://lab.uberspace.de/guide_postgresql/)
- [U7 7.15.3: pgvector fuer PostgreSQL 12–15](https://github.com/Uberspace/manual/blob/main/source/changelog/2023-06-19_7.15.3.rst)
- [U7 Webbackends](https://manual.uberspace.de/web-backends/)
- [U7 Python](https://manual.uberspace.de/lang-python/)
- [U7 Ressourcen](https://manual.uberspace.de/basics-resources/)
- [pgvector: Installation, Datentypen und Distanzoperatoren](https://github.com/pgvector/pgvector)
- [U7/U8-Plattformvergleich des Anbieters](https://u8manual.uberspace.de/landingpage_features/)
- [U8 PostgreSQL und Erweiterungen](https://u8manual.uberspace.de/database_postgresql/)

Projektbezug: `ki_knowledge/integrations/knowledge_store.py`
(`_init_schema`, `add_embedding`, `similar_blocks`),
`ki_knowledge/config_runtime.py`, `config/defaults/stack.yaml` und
`ki_knowledge/django_site/settings.py`. Gemeinsame offene Integrationspunkte
sind im [U8-Leitfaden](UBERSPACE8_IMPLEMENTATION.md) dokumentiert.
