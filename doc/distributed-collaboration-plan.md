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
