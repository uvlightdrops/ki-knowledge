---
project: ki-knowledge
agent_project: ki-knowledge
scope: guides
created: "2026-09-02 18"
updated: "2026-11-08 00"
update_reason: "Stackctl-Schnellstart an führende Dokumentation und Projekt-venv angepasst"
status: active
semantic_blocks:
  - quick-start
  - initial-setup
  - important-urls
  - start-options
  - database
  - troubleshooting
  - tips
  - workflow
  - environment-overrides
  - conclusion
---

# 🚀 Django Dev - Quick Start Guide

YAML-Schichten, Editor-Grenzen und projektuebergreifende Bedienung:
[YAML_CONFIG_SYSADMIN.md](YAML_CONFIG_SYSADMIN.md). Der aktuelle Editor-Code ist
kein Nachweis eines getesteten oder installierten Rollouts. Generisches
Engineering: [yaml-cfg-wizard](../../../yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md).

<a id="-schnellstart"></a>
<a id="quick-start"></a>
## Schnellstart [quick-start]

```bash
# Im ki-knowledge-Projekt: vorhandene Projekt-venv mit stackctl verwenden.
.venv/bin/python -m stackctl spec
.venv/bin/python -m stackctl start
.venv/bin/python -m stackctl status
.venv/bin/python -m stackctl logs django -f
.venv/bin/python -m stackctl stop

# Ein lokaler Dienst im Vordergrund; Abhängigkeiten müssen bereit sein:
.venv/bin/python -m stackctl run django
.venv/bin/python -m stackctl run api

# Kompatibilitätseinstiege:
./kistack run django
python examples/run_knowledge_django.py
python examples/run_knowledge_api.py

# Direkter Django-Aufruf (umgeht die Stack-Konfiguration, aktivierte venv):
python manage.py migrate
python manage.py runserver
```

Installation, Aufrufvarianten und allgemeines Verhalten stehen in der
[stackctl-Dokumentation](../../../stackctl/README.md) und ihrem
[Betriebsleitfaden](../../../stackctl/doc/OPERATIONS_GUIDE.md). Standard im
KI-Ecosystem ist der Aufruf aus der Projekt-venv; `stackctl install` erstellt
diese venv nicht. `spec` kann vertrauliche Konfigurationswerte enthalten und
ist kein Start-Dry-Run.

`kistack` bleibt ein projektgebundener Kompatibilitätsalias, auch als Symlink:
zuerst `.venv/bin/python -m stackctl`, ohne Projektinterpreter
`~/.local/bin/stackctl` und danach `stackctl` aus dem PATH. Er setzt
das Arbeitsverzeichnis auf dieses Projekt und reicht Argumente/Exitcode durch.
Er installiert oder klont nichts und legt selbst keine `.venv` mehr an;
das macht bei Bedarf ausschließlich `stackctl install`. Fehlt das Tool,
bricht der Alias mit Installationshinweis ab. Die alten Python-Launcher
delegieren nur über diesen Alias zu `stackctl -t local run api|django`;
ihre bestehenden `KI_API_*`-Overrides bleiben kompatibel.

Der Stack steht in `config/defaults/stack.yaml` (Abschnitt `stack:`). Er wird über ki-core
geladen, Stages und `KI_CFG_*`-Env gelten also auch hier.

Die API startet direkt als `python -m uvicorn ki_knowledge.api.knowledge_app:app`;
das Example-Skript enthaelt keine eigene Uvicorn-Konfiguration mehr. Reload wird
ueber `stack.services.api.env.UVICORN_RELOAD` gesteuert (Entwicklung: true,
Prod/Cluster: false). Alte `KI_API_HOST`, `KI_API_PORT`, `KI_API_RELOAD` werden
beim Aufruf des API-Example-Skripts auf die passenden `KI_CFG_STACK__*`-Overrides
abgebildet; explizite neue Overrides haben Vorrang. Django hat bewusst keine
harte API-Abhaengigkeit: nicht jede UI-Funktion braucht die API.

Mit `start` gestartete Dienste laufen losgelöst vom Terminal weiter. `stop` beendet auch von Hand
gestartete Server, aber nur, wenn sie aus diesem Projekt stammen. Ein fremder Prozess auf
dem Port bleibt unangetastet. Postgres kommt bei Bedarf per docker compose aus
`deploy/postgres` (`.env` nötig), Ollama genauso aus `deploy/ollama`. Danach lädt
`ki_knowledge.ollama_models` fehlende Modelle: `knowledge.embed_model`, bei
`provider: ollama` auch das Chat-Modell.

Django bekommt `KNOWLEDGE_API_URL` passend zum API-Port. Auch der Prod-Host läuft mit
`runserver --insecure`, damit statische Dateien ohne DEBUG funktionieren. Das ist bewusst
einfach gehalten und nicht für das offene Internet gedacht.

### Wagtail-Kataloge explizit einrichten

Nach Anlage neuer InfoSite-Projekte bei Bedarf im Projekt mit aktivierter
`.venv` und der gewünschten Host-/Stage-Konfiguration ausführen:

```bash
python manage.py setup_wagtail_cms
```

Das Kommando legt fehlende Katalog- und Detailseiten für aktivierte Projekte
an und veröffentlicht **nur neu angelegte** Seiten. Wiederholungen verändern
keine bestehenden Texte, Revisionen oder Veröffentlichungszustände.
Vorhandene Entwürfe im CMS prüfen/veröffentlichen. Ohne konfigurierte
Standard-Wagtail-Site bricht das Kommando mit einem Fehler ab.

Öffentliche Seitenaufrufe lesen nur: Sie ersetzen dieses Setup nicht,
erzeugen keinen Blockstore und starten keine Extraktion. Fehlt der
Blockspeicher, zeigt der Katalog einen Fehler statt „0 Blöcke“.
InfoSite-Extraktion bleibt ein eigener Pipeline-Schritt. Details zu den
[führenden Speichern und Redaktionsgrenzen](../architecture/CONTENT-MODEL-MATRIX.md#0-verbindliche-speicher--und-adaptergrenze-p2).

### Stages und Host-Overrides

Pro Host einmal festlegen (die Datei ist nicht in git; `KI_STAGE=…` hat Vorrang):

```bash
echo dev-lokal > config/stages/.active_stage   # dev-lokal | prod (dev-mk/prod-k8s setzt der Cluster)
```

Rangfolge in ki-core, höchste zuerst:

1. `creds.yaml`
2. Env `KI_CFG_*`
3. `config/runtime/runtime.yaml`
4. aktive Stage
5. aktives Profil (`KI_PROFILE` oder `config/profiles/.active_profile`)
6. `ki.yaml`
7. `config/defaults/`
8. Schema-Defaults

Daraus folgt:

- Die Stage schlägt `ki.yaml`. Host-spezifische Werte, die die Stage **nicht** setzt (ki
  `base_url`, DSN, `secret_key`, `allowed_hosts`), gehören in `ki.yaml`.
- Abweichungen von Stage-Werten gehören in `config/runtime/runtime.yaml` (nicht in git)
  oder in Env. Beispiel für andere Ports:

```bash
KI_CFG_STACK__SERVICES__DJANGO__PORT=8011 KI_CFG_STACK__SERVICES__API__PORT=8091 stackctl start
```

#### Sync-Felder im Browser pflegen (`/settings/config/sync/`)

Superuser können dort wenige Sync-/Remote-Collaboration-Felder im Runtime-Layer
(`config/runtime/runtime.yaml`, nur unterhalb des Projektverzeichnisses, keine Symlinks) setzen
oder entfernen. Grundlage ist `yaml_cfg_wizard.editor`; Schreibzugriff braucht den optionalen
Django-Adapter:

```bash
pip install -e '../yaml_cfg_wizard[django]'   # Editor-Core ab Version 0.2.0
pip install -e '.[config-editor]'
```

Ohne importierbaren Editor/Adapter bleibt die Seite read-only (POST -> 405).
Das Extra deklariert die Abhängigkeit, ist aber kein Laufzeit-Featureflag:
mit yaml-cfg-wizard 0.2.0 und vorhandenem Django ist der Adapter verfügbar.
Nach dem Code-/Paketupdate Django einmal mit `stackctl restart django` neu laden;
spätere Änderungen dieser beiden YAML-Felder brauchen keinen Neustart.

- Editierbar (Allowlist): `apps.ki_knowledge.distributed.public_url` (nur `http(s)://host[:port][/pfad]`,
  ohne Zugangsdaten/Query/Fragment) und `apps.ki_knowledge.distributed.federation_id`.
- Gespeichert wird nur, wenn die **vollständig** neu aufgelöste Config (Runtime-Layer ersetzt,
  Env und `creds.yaml` weiterhin darüber) gegen das gemergte Schema valide ist; parallele
  Änderungen ergeben einen Konflikt (409). „Entfernen“ löscht den Override, `""` setzt einen leeren String.
- Nicht editierbar: `node_role`, `enabled`, `sync_on_connect`, `master_url`, `sync_shared_secret`.
  Sobald ein `NodeConfig`-Eintrag für den lokalen Node existiert, hat die DB Vorrang; diese Werte
  pflegt die Sync-Administration (`/admin-overview/sync/`). `node_id`, DSN und Secrets werden nie
  angezeigt oder geändert.
- Wirkung ohne Neustart: `public_url`/`federation_id` werden pro Aufruf aus der aufgelösten Config
  gelesen (Descriptor, Heartbeat, Federation-Prüfung).
- YAML-Werte außerhalb der Allowlist bleiben erhalten; Kommentare und Formatierung werden
  beim atomaren Speichern neu geschrieben. Die `.editor.lock`-Datei ist ein dauerhaftes
  Advisory-Lock; externe Schreiber müssen sie ebenfalls beachten.

### minikube / Kubernetes

```bash
stackctl -t minikube start    # Profil ki-knowledge (4 CPU, 8 GB), Image bauen+laden, helm --wait
stackctl -t minikube status   # Pods/PVCs + URL (NodePort von Django)
stackctl -t minikube logs django
stackctl -t minikube stop     # Release weg, PVCs (Postgres, /data) bleiben
stackctl -t minikube delete   # inkl. Namespace und Daten
```

- **dev-mk** (Stage in den Pods): Postgres, Ollama, API und Django laufen im Cluster.
  Chat und Embeddings nutzen `http://ollama:11434`, nicht das Host-Netz.
  Der Job `ollama-post-start-<revision>` lädt die benötigten Modelle automatisch;
  sie bleiben auf der PVC `ollama-models` erhalten. Beim ersten Start benötigt das
  Herunterladen Internetzugang und zusätzliche Plattenkapazität. Ollama läuft
  ohne GPU-Anbindung auf der CPU; der erste Chat kann entsprechend länger dauern.
  `helm --wait` wartet auf die Dienste, nicht auf den Abschluss des Model-Pull-Jobs:
  `kubectl --context ki-knowledge -n ki-knowledge get jobs` zeigt dessen Status.
- **prod-k8s:** `stack.k8s.registry` und `context` setzen, optional `ingress`. Die
  Kommentare stehen in `stack.yaml` unter `targets.k8s`.
- Secrets:
  - `deploy/postgres/.env` wird zum Secret `ki-knowledge-env`.
  - `creds.yaml` wird nach `/app/creds.yaml` gemountet.
  - Die DSN baut sich aus `$(KI_PG_*)` zusammen. Sie gehört deshalb nicht in `creds.yaml`.

Nach Start: **http://localhost:8000**

### Prod: firmeninterne KI + lokales Ollama für Embeddings

Gleiche Konfig-Linie wie ki-core / kicli-code-assist: `llm.provider` wählt den
Chat-Provider (`ki` | `ollama` | `openai` | `mock`), Embeddings laufen immer über Ollama
(`nomic-embed-text`, damit die Vektoren zwischen Hosts vergleichbar bleiben).

Die mitgelieferten Stages verwenden den aktuellen ki-core-Schluessel `llm.provider`.
Ein alter Host-Override `llm.default_provider` muss entsprechend umbenannt werden;
das aktuelle Core-Schema lehnt ihn ab. Das interne Python-Attribut
`AppConfig.llm_default_provider` bleibt fuer bestehende Aufrufer erhalten.

```bash
echo prod > config/stages/.active_stage   # provider ki, debug false, Django auf 0.0.0.0
```

```yaml
# ki.yaml (Prod) – nur hostspezifische Werte
llm:
  providers:
    ki:
      base_url: https://ki.firma.intern/v1   # OpenAI-kompatibel
      model: google/gemma-4-26B-A4B-it
    ollama:
      base_url: http://127.0.0.1:11434       # Docker aus deploy/ollama
http:
  verify_ssl: true                           # Firmen-CA: Env REQUESTS_CA_BUNDLE=/pfad/ca.pem
apps:
  ki_knowledge:
    distributed:
      postgres_dsn: postgresql://ki_knowledge:<pw>@127.0.0.1:5432/ki_knowledge
    django:
      secret_key: "<zufällig>"
      allowed_hosts: [kihost.lan, localhost]
      wagtail_admin_base_url: http://kihost.lan:8000
```

```yaml
# creds.yaml (nicht in git)
llm:
  providers:
    ki:
      api_key: "<token>"
```

Danach `stackctl start` – Postgres und Ollama kommen als Container, das Embedding-Modell
wird beim ersten Start geladen. Der Chat (`/knowledge/chat/ollama/`) zeigt den aktiven Provider.

---

<a id="-setup-erste-mal"></a>
<a id="initial-setup"></a>
## Setup beim ersten Mal [initial-setup]

### Schritt 1: Migrations ausführen
```bash
python manage.py migrate
```

### Schritt 2: Admin-Benutzer erstellen
```bash
python manage.py createsuperuser
```

Interaktive Eingaben:
- Username: `admin`
- Email: `admin@example.com`
- Password: (sicher wählen)

### Schritt 3: Server starten
```bash
python manage.py runserver
```

---

<a id="-wichtige-urls"></a>
<a id="important-urls"></a>
## Wichtige URLs [important-urls]

| URL | Beschreibung |
|-----|-------------|
| `http://localhost:8000/` | Startseite |
| `http://localhost:8000/admin/` | Admin Panel |
| `http://localhost:8000/data-sources/` | Quellen und Import |
| `http://localhost:8000/knowledge/workbench/` | Textwerkstatt |
| `http://localhost:8000/output/infosite/` | InfoSite-Projekte |

---

<a id="-verschiedene-startoptionen"></a>
<a id="start-options"></a>
## Verschiedene Startoptionen [start-options]

### Default (Port 8000)
```bash
python manage.py runserver
```

### Custom Port
```bash
python manage.py runserver 8001
python manage.py runserver 8080
```

### Alle Hosts (für Remote/Docker)
```bash
python manage.py runserver 0.0.0.0:8000
```

### Mit Debugging und Auto-Reload
```bash
python manage.py runserver --nothreading
```

---

<a id="-datenbank-struktur"></a>
<a id="database"></a>
## Datenbankstruktur [database]

Die Datenbank hängt von der aufgelösten Konfiguration ab: Eine konfigurierte
PostgreSQL-DSN aktiviert PostgreSQL; andernfalls wird SQLite verwendet.
Der SQLite-Pfad wird aus Datenwurzel und Datenlayout bestimmt und kann
über `DJANGO_DB_PATH` überschrieben werden.

**Tabellen:**
- `django_session` - Session-Daten
- `auth_user` - Benutzer
- `auth_group` - Gruppen
- `django_site_infositeproject` - Infosite Projekte
- `django_site_sourcedocument` - Quelldokumente

---

<a id="-troubleshooting"></a>
<a id="troubleshooting"></a>
## Troubleshooting [troubleshooting]

### "no such table: django_session"
```bash
python manage.py migrate
```

### "django.core.exceptions.ImproperlyConfigured"
```bash
export DJANGO_SETTINGS_MODULE=ki_knowledge.django_site.settings
python manage.py runserver
```

### Admin-Login funktioniert nicht
```bash
python manage.py createsuperuser
```

---

<a id="-tipps"></a>
<a id="tips"></a>
## Tipps [tips]

✅ Immer mit Virtual Environment starten:
```bash
source .venv/bin/activate
```

✅ Migrations vor Datenbankänderungen:
```bash
python manage.py makemigrations
python manage.py migrate
```

✅ Django Shell für schnelle Tests:
```bash
python manage.py shell
>>> from ki_knowledge.django_site.infosite_models import InfoSiteProject
>>> InfoSiteProject.objects.all()
```

✅ Statische Dateien sammeln:
```bash
python manage.py collectstatic --noinput
```

---

<a id="-workflow"></a>
<a id="workflow"></a>
## Workflow [workflow]

```
1. venv aktivieren
   source .venv/bin/activate

2. Migrations ausführen
   python manage.py migrate

3. Server starten
   python manage.py runserver

4. Browser öffnen
   http://localhost:8000/admin/

5. Infosite nutzen
   http://localhost:8000/output/infosite/
```

---

<a id="-environment-variables"></a>
<a id="environment-overrides"></a>
## Environment Variables [environment-overrides]

Normalerweise nicht nötig – Django-Werte stehen in `ki.yaml` unter
`apps.ki_knowledge.django.*`. Umgebungsvariablen überschreiben sie pro Prozess:

```bash
export DJANGO_DB_PATH=/custom/path/django.sqlite3
export DJANGO_SECRET_KEY=your-secret-key-here
export DJANGO_DEBUG=true
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export KI_CFG_LLM__PROVIDER=mock   # ki-core-Override: KI_CFG_<pfad mit __>
```

---

<a id="-fertig"></a>
<a id="conclusion"></a>
## Fertig [conclusion]

Die Django Site ist jetzt ready für Development. Viel Erfolg! 🎉
