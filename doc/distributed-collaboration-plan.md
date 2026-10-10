# Distributed Collaboration Plan

## Zielbild

- **Ein Master-Knoten** ist die zentrale Autorität für persistente Metadaten und Sync-Annahmen.
- **Weitere Hosts** dürfen neue Domains lokal anlegen und offline daran arbeiten.
- Sobald ein Host wieder online ist, **übermittelt** er seinen Stand an den Master.
- **PostgreSQL** ersetzt SQLite für die zentrale Django-Datenbank; lokale SQLite-Stores bleiben vorerst nur als Cache/Edge-Zwischenspeicher bestehen.

## Umsetzungsphasen

1. **Foundation**
   - Node-Rollen (`master`, `host`, `standalone`) konfigurierbar machen.
   - Domain-Ownership einführen: `home_node`, `sync_mode`, `visibility`, `last_sync_at`.
   - PostgreSQL in Django optional per DSN aktivieren.

2. **Master Registry + Domain Claims**
   - Master-API für Domain-Registrierung und Heartbeats.
   - Hosts melden neue Domains an und erhalten Ownership-/Visibility-Regeln zurück.
   - Konfliktregel: pro Domain genau ein `home_node`.

3. **Outbound Sync vom Host zum Master**
   - Änderungslog oder Snapshot-Export für:
     - `InfoSiteProject`
     - `SourceDocument`
     - Domain-Metadaten
     - Knowledge-Store-Quellen/Records/Artefakte
   - Idempotente Upserts auf dem Master.

4. **Inbound Pull / Rehydration**
   - Hosts können Domain-Metadaten und relevante Inhalte vom Master erneut beziehen.
   - Selektive Replikation statt globalem Vollabzug.

5. **SQLite-Ablösung im Kern**
   - `KnowledgeStore` und Job-Historien hinter Storage-Interfaces ziehen.
   - PostgreSQL-Implementierungen ergänzen.
   - SQLite nur noch für lokale Caches/offline queues.

## Erste konkrete Architekturentscheidungen

- **Source of truth**
  - Master-PostgreSQL für Django-/Domain-Metadaten.
  - Domain-Inhalte bleiben vorerst dateibasiert, werden aber über Ownership und Sync-Zeitpunkte verwaltet.
- **Offline-first**
  - Hosts dürfen disconnected arbeiten.
  - Synchronisation ist zunächst **host → master**.
- **Konfliktarm starten**
  - Keine Multi-Master-Semantik.
  - Eine Domain gehört genau einem Home Node.
- **Interne API-Absicherung**
  - Sync-Endpunkte werden zuerst per gemeinsamem Secret abgesichert.
  - Header `X-KI-Sync-Secret` ist der bevorzugte Transport.

## Direkt danach im Repo

1. Master-/Host-spezifische Admin-Ansicht erweitern.
2. `NodeConfig` in Domain-Management und Status-Seiten anzeigen.
3. Eine kleine Sync-API-Spezifikation für Domain-Register/Heartbeat/Push festziehen.
4. Danach die erste Push-Route und Export-Payload implementieren.

## Aktueller Stand

- Foundation für Domain-Ownership und Node-Registry ist umgesetzt.
- Export/Push für `InfoSiteProject` und `SourceDocument`-Metadaten ist vorhanden.
- Sync-Endpunkte können jetzt optional per `apps.ki_knowledge.distributed.sync_shared_secret`
  geschützt werden.
- Admin-UI enthält jetzt ein dediziertes **Distributed Sync Center** unter
  `/admin-overview/sync/` mit:
  - lokaler Node-Konfiguration
  - Host-seitigem Master-Domain-Katalog
  - Sync-Historie und Job-Steuerung
  - Master-seitiger **Host-Registry** mit Remote-Pull-Trigger für die aktive Domain

## Laufender Mechanismus

### Host → Master Sicht

- Hosts konfigurieren:
  - `role=host`
  - `base_url=<master-base-url>`
  - `sync_shared_secret`
- Hosts können vom Master einen Domain-Katalog abrufen (`/knowledge/sync/export/`
  mit `include_* = 0`) und selektiv Domains übernehmen.
- Danach zieht der Host die Domain per `POST /knowledge/sync/pull/` vom Master.

### Master → Host Sicht

- Der Master führt eine Registry bekannter Nodes in `NodeConfig`.
- Einträge entstehen durch:
  - lokale Konfiguration
  - Heartbeats / eingehende Sync-Kommunikation
- Im Sync-Center kann der Master bekannte Hosts sehen:
  - `node_id`
  - `display_name`
  - `role`
  - `base_url`
  - `last_seen_at`
- Der Master kann einem Host für die **aktive Domain** einen Remote-Pull auslösen.
  Technisch ist das kein Daten-Push, sondern ein **Master-initiiertes Pull-Kommando**:
  der Master ruft auf dem Host `POST /knowledge/sync/pull/` auf, damit der Host
  die Domain vom Master holt.

## Gemeinsame Grundlagen mit ia3simworld

Im Vergleich zu `ia3simworld` zeigen sich wiederkehrende Bausteine, die sich
projektübergreifend modularisieren lassen:

1. **Node Identity**
   - eindeutige `node_id`
   - `display_name`
   - `base_url`
   - Rolle (`master` / `host` bzw. föderierter Knoten)

2. **Node Registry**
   - Master hält bekannte Nodes zentral vor
   - Nodes registrieren oder melden sich periodisch zurück
   - `last_seen_at` / Health-Sicht ist essenziell

3. **Master-only Controls**
   - globale Steuerung nur vom Master
   - Satelliten/Hosts führen aus, bleiben aber nicht autoritativ

4. **Remote Trigger statt Voll-Push**
   - Master stößt Aktionen auf Hosts an
   - Hosts holen oder verarbeiten Daten selbst
   - reduziert Kopplung und hält Ownership klar

5. **HTTP-Control Plane + lokale Worker/Data Plane**
   - kleine autorisierte HTTP-Endpunkte für Steuerung
   - eigentliche Verarbeitung in Jobs/Runnern lokal pro Node

### Sinnvolle spätere Modularisierung

Eine gemeinsame Distributed-Basis könnte später in ein separates Modul
extrahiert werden, z. B. mit:

- `NodeIdentity`
- `NodeRegistryService`
- `HeartbeatService`
- `RemoteCommandClient`
- `MasterOnlyPolicy`
- `NodeHealthSnapshot`

## Interne API-Grenzen im aktuellen Repo

Vor einer Auslagerung in ein eigenes Paket läuft die Entkopplung jetzt über
eine interne API-Datei:

- `ki_knowledge.django_site.distributed_api`

Diese Schicht kapselt die aktuellen Distributed-Funktionen in stabilere
Aufrufergruppen:

1. **Node Identity / Runtime Config**
   - `get_local_node_snapshot()`
   - `ensure_local_node()`
   - `get_master_url()`
   - `get_sync_secret()`

2. **Payload Export**
   - `export_local_sync_payload()`
   - `export_knowledge_sync_payload()`
   - `export_sync_snapshot()`

3. **Inbound Import**
   - `import_remote_heartbeat()`
   - `import_remote_domain_sync()`

4. **Remote Commands**
   - `pull_domains_from_master()`
   - `fetch_master_domain_catalog()`
   - `send_host_pull_command()`

5. **Registry**
   - `list_known_hosts()`

Ziel ist, dass Views/Runner künftig bevorzugt diese API nutzen und nicht mehr
direkt die tiefe Implementierung in `distributed_sync.py`. Damit wird die
spätere Extraktion in ein separates Paket weitgehend mechanisch.

## Reifekriterien vor Paket-Extraktion

Vor der Auslagerung in ein neues Projekt sollen folgende Bedingungen erfüllt sein:

1. **Primäre Runtime-Quelle geklärt**
   - Laufende Distributed-Einstellungen kommen primär aus `NodeConfig`
   - `AppConfig` bleibt Fallback für Bootstrapping und Defaults

2. **Heartbeat-Loop vorhanden**
   - Hosts können aktiv Heartbeats an den Master senden
   - Master-Registry basiert nicht nur auf passiven Sync-Nebeneffekten

3. **Views nutzen die interne API**
   - keine direkte Kopplung von UI/Runnern an tiefe Implementierungsdetails

4. **Payload-Logik und generische Control-Plane getrennt**
   - generische Node/Registry/Command-Themen sind von
     `InfoSiteProject`-/Knowledge-Payloads trennbar

## Aktueller Reifegrad

- Runtime-Zugriff wird jetzt über `distributed_api.get_runtime_node_settings()`
  vereinheitlicht: `NodeConfig` zuerst, `AppConfig` als Fallback.
- Persistenz der lokalen Node-Einstellungen läuft über
  `distributed_api.persist_local_node_settings()`.
- Beim Speichern werden die aufgelösten Node-Einstellungen zusätzlich in die
  laufende Prozesskonfiguration übernommen, sodass `NodeConfig` nicht nur
  persistent in der DB liegt, sondern auch sofort die aktive Runtime-Quelle ist.
- Hosts können manuell Heartbeats an den Master senden; damit wird die
  Host-Registry aktiv gepflegt und nicht nur indirekt.
- Die generische Control-Plane wird weiter vom Payload-Sync getrennt:
  - Registry / Heartbeat / Remote Commands in `distributed_api`
  - Domain-/Knowledge-spezifische Replikationslogik weiterhin in `distributed_sync`

Der nächste sinnvolle Schritt vor einer echten Auslagerung ist dann vor allem:

- Heartbeats automatisch/intervallgesteuert senden
- generische Registry-/Command-Typen weiter komplett von Domain-Payloads ablösen

Für `ki-knowledge` ist der nächste pragmatische Schritt:

- `NodeConfig` als primäre Runtime-Quelle etablieren
- Heartbeat aktiv vom Host aus senden
- Host-Registry um Health/Capabilities erweitern
- Remote-Kommandos als explizite Command-Typen modellieren

## Gemeinsame Node-Basis mit ia3simworld (ki-node-core)

Konzept: `ia3simworld/docs/ki-cooperation/shared-node-sync.md`. Die Pakete
`ki-node-core` und `ki-node-http` liegen dort vorbereitend unter `packages/`.
ki-knowledge ist vorbereitet (Stand 2026-10-09). Bestehende Endpoints und deren
Verhalten bleiben gleich, alle Erweiterungen sind additiv.

**Adapterschicht `ki_knowledge/node_sync/`** (frameworkfrei, ohne Django-Import):

| Modul | Inhalt |
|---|---|
| `settings.py` | `NodeSettings`: aufgelöste Node-Einstellungen, Heartbeat-Body (alt + additive Felder) |
| `capabilities.py` | Protokoll `0.1` (= heutige `/knowledge/sync/*`-Endpoints), Capabilities je Rolle |
| `descriptor.py` | `describe()` als JSON; `to_descriptor()` → `ki_node_core.NodeDescriptor` (Extra `node`) |
| `client.py` | `SyncClient`: alle ausgehenden Sync-Requests (Heartbeat, Export, Pull-Command) |

Django baut über `distributed_api.get_node_settings()` die `NodeSettings`.
`distributed_sync` nutzt nur noch `SyncClient` und baut keine Requests mehr selbst.

| Capability | Rollen | Endpoint |
|---|---|---|
| `knowledge.node.describe@1.0` | alle | `GET /knowledge/sync/node/` (neu, ohne Secrets) |
| `knowledge.node.heartbeat@1.0` | master | `POST /knowledge/sync/heartbeat/` |
| `knowledge.snapshot.export@1.0` | alle | `GET /knowledge/sync/export/` |
| `knowledge.snapshot.import@1.0` | master | `POST /knowledge/sync/push/` |
| `knowledge.domain.pull@1.0` | host | `POST /knowledge/sync/pull/` (Remote Command) |

**Abbildung auf die gemeinsamen Begriffe:**

- `node_id` bleibt stabil. `instance_id` ist neu pro Prozessstart.
- `federation_id` kommt aus `apps.ki_knowledge.distributed.federation_id` (Standard `default`).
  Ein Heartbeat aus einer fremden Föderation wird mit 400 abgelehnt. Ältere Hosts
  ohne das Feld werden weiter akzeptiert.
- `NodeConfig.base_url` bedeutet auf einem **Host** die Master-URL, also den
  `coordinator_endpoint`. Die eigene erreichbare Adresse ist neu
  `distributed.public_url` (`endpoint`). Nur wenn sie gesetzt ist, meldet der
  Heartbeat sie als `base_url`. Ohne sie bleibt das alte Verhalten: Der Master
  speichert die Master-URL als Host-Adresse, und `trigger_host_pull` kann den
  Host dann nicht erreichen. **Auf Hosts `public_url` setzen.**
- Remote Command `knowledge.domain.pull` bekommt eine `operation_id`, als Header
  `X-KI-Operation-Id` und als Formularfeld. Der Host gibt sie im Ergebnis zurück.
  Deduplizierung und Leases gibt es noch nicht (siehe `CommandStore` im Konzept).

**Nebenbei behoben** (Funde beim Live-Test):

- Die POST-Endpoints heartbeat, push und pull lieferten 403 wegen CSRF. Zwischen
  Maschinen funktionierten sie also nicht. Jetzt `csrf_exempt`, authentifiziert
  über `X-KI-Sync-Secret`. Ohne Secret werden Cross-Site-Browser-Requests abgelehnt.
- Export/Katalog: Die `include_*`-Schalter überspringen jetzt die Arbeit, statt
  Ergebnisse zu verwerfen. Das Wissen wurde vorher doppelt berechnet. Der Katalog
  braucht damit 0,05 s statt 49 s, `sync/status` ebenso.

**Hinweise für ki-node-http / ia3simworld:**

- `HttpConfig` erlaubt http nur für Loopback. Bestehende ki-knowledge-Föderationen
  laufen per http im LAN, deshalb nutzt `SyncClient` vorerst weiter `requests`.
  Vorschlag: eine explizite Option für private Netze oder TLS-Pflicht ab Protokoll 1.0.
- Das Secret ist heute ein geteiltes Secret im Header (`X-KI-Sync-Secret`). Die
  Abbildung auf `CredentialProvider` und node-spezifische Credentials ist offen.
- Für den Pilot (freigegebenes Wissens- oder Profilartefakt nach SimWorld) fehlen
  noch: Wire-Schema für `TransferEnvelope`, Digest-Profil, Revisionen je Ressource
  und eine Inbox mit Deduplizierung.

Lokal (Extra `node`, noch nicht auf PyPI):
`.venv/bin/pip install -e ../ia3simworld/packages/ki-node-core`. Ohne das Paket
läuft alles weiter, nur `to_descriptor()` fehlt dann. Tests: `tests/test_node_sync.py`.

## PostgreSQL-Umstellung

### Stufe 1 – Django-/Wagtail-DB (umgesetzt)

- Server: `deploy/postgres/docker-compose.yml` (`pgvector/pgvector:pg16`, Extension `vector`
  per `initdb/`). Zugangsdaten in `deploy/postgres/.env` (nicht versioniert, Vorlage `.env.example`),
  Datenverzeichnis `<data-root>/system/postgres`, standardmäßig nur an `127.0.0.1` gebunden.
  Start: `cd deploy/postgres && docker compose up -d`.
- Tabellen-Browser (optional): `docker compose --profile tools up -d pgadmin` → http://127.0.0.1:5050
  (pgAdmin 4, Einzelplatzmodus ohne Login, nur lokal erreichbar; Server „ki-knowledge“ ist vorkonfiguriert).
- Django nutzt PostgreSQL, sobald `KI_KNOWLEDGE_POSTGRES_DSN` oder
  `apps.ki_knowledge.distributed.postgres_dsn` (lokale `ki.yaml`) gesetzt ist; dann ist auch
  `django.contrib.postgres` aktiv. Ohne DSN bleibt SQLite (Tests, Edge-Hosts).
- Datenübernahme: `python manage.py migrate_django_db_to_postgres` (Probelauf), danach
  `--apply --confirm-services-stopped` (`--replace` überschreibt ein bereits befülltes Ziel).
  Primärschlüssel und ContentTypes werden 1:1 übernommen (Wagtail referenziert Objekte über
  Text-IDs), Zeilenzahlen pro Modell werden verglichen, der Suchindex wird neu aufgebaut.
  Die SQLite-Datei bleibt unverändert als Backup, zusätzlich ein JSON-Export in `system/`.
- Migration `0007_backfill_domain_registry` kapselt den Aufruf von Live-Code in einen
  Savepoint, damit frische PostgreSQL-Installationen migrieren.

### Stufe 2 – KnowledgeStore und SemanticTerms

- `KnowledgeStore`, `KnowledgeGraph` und `SemanticTermStore` laufen über ein gemeinsames
  Backend (`sql_backend`): lokal weiter SQLite, bei konfigurierter PostgreSQL-DSN PostgreSQL.
- Schema-Layout in PostgreSQL: globale Wissensdaten in `knowledge`, SemanticTerms je Domain in
  `semantic_<domain>` (normalisiert und kollisionssicher gekürzt). JSON-Felder werden als `jsonb`
  gespeichert, Embeddings als `pgvector`.
- Auswahl: `KI_KNOWLEDGE_POSTGRES_DSN` bzw. `distributed_postgres_dsn`; Escape-Hatch
  `KI_KNOWLEDGE_STORE_BACKEND=sqlite` erzwingt SQLite (auch für Tests/Notfallbetrieb).
- Migration: `python manage.py migrate_knowledge_store_to_postgres` ist Dry-Run; echte Kopie nur mit
  `--apply --confirm-services-stopped`, erneut befüllbar mit `--replace`, optional `--domain`
  bzw. `--knowledge-only`. Domains ohne Cache-Datei werden übersprungen; ihr Schema entsteht bei
  der ersten Nutzung. Am 2026-10-08 übernommen: 126.169 Zeilen (knowledge + anthro/eakte),
  Zählungen und Stichproben (source_stats, Suche, Semantic-Totals) identisch zu SQLite.
- SQLite bleibt zuständig für lokale Offline-/Cache-Daten: Job-Queues (`pdf_import_jobs`,
  `pipeline_jobs`, Sync-Jobs), JiraCache-Tabellen, Jira-Graph und `block_store.db`.
