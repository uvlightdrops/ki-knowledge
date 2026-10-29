# 🚀 Django Dev - Quick Start Guide

YAML-Schichten, Editor-Grenzen und projektuebergreifende Bedienung:
[YAML_CONFIG_SYSADMIN.md](YAML_CONFIG_SYSADMIN.md). Der aktuelle Editor-Code ist
kein Nachweis eines getesteten oder installierten Rollouts. Generisches
Engineering: [yaml-cfg-wizard](../../../yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md).

## ⚡ SCHNELLSTART

```bash
# Voraussetzung: globales stackctl installiert, ~/.local/bin im PATH.
# Einmalig im stackctl-Checkout: ./scripts/install-user.sh
# Im ki-knowledge-Projekt:
stackctl install        # Projekt-.venv + Geschwister-Repos + Projekt (siehe README)
# Option 1: ganzer Stack (Postgres, Ollama-Check, API :8090, Django :8000)
stackctl start          # startet nur, was noch nicht läuft (Django: migrate + runserver)
stackctl status         # was läuft, PIDs, URLs
stackctl stop           # verwaltete Dienste stoppen, Daten bleiben erhalten
stackctl restart django # einzelne Dienste: postgres | ollama | api | django
stackctl logs django -f # Logs unter var/log/, PIDs unter var/run/
stackctl spec           # aufgelöste Stack-Spec (Ports, Kommandos, Env)

# Option 2: Einzelner Dienst im Vordergrund (gleiche Konfiguration wie start)
stackctl run django     # migrate + runserver; Strg+C beendet den Dienst
stackctl run api        # alternativ: API im Vordergrund
# Andere benötigte Dienste bei Bedarf separat: stackctl start api

# Nur Kompatibilität, keine eigenen Server-Implementierungen:
./kistack run django
python examples/run_knowledge_django.py
python examples/run_knowledge_api.py

# Direkter Django-Aufruf (umgeht die Stack-Konfiguration):
python manage.py migrate
python manage.py runserver
```

Der Haupteinstieg ist das zentrale [stackctl](../../../stackctl/README.md),
aufgerufen im Projektverzeichnis oder einem Unterverzeichnis. Seine eigene
Tool-venv ist von der Projekt-.venv getrennt: Konfigurationsloader und
`{python}`-Dienstkommandos laufen mit dem Projektinterpreter. Eine Aktivierung
der Projekt-.venv ist für den globalen Aufruf nicht erforderlich.

`kistack` bleibt ein projektgebundener Kompatibilitätsalias, auch als Symlink:
zuerst `~/.local/bin/stackctl`, andernfalls `stackctl` aus dem PATH. Er setzt
das Arbeitsverzeichnis auf dieses Projekt und reicht Argumente/Exitcode durch.
Er installiert oder klont nichts und legt selbst keine `.venv` mehr an;
das macht bei Bedarf ausschließlich `stackctl install`. Fehlt das Tool,
bricht der Alias mit Installationshinweis ab. Die alten Python-Launcher
delegieren nur über diesen Alias zu `stackctl -t local run api|django`;
ihre bestehenden `KI_API_*`-Overrides bleiben kompatibel.

Dies entspricht der aktuellen Assist-Anbindung: `kicli-assist server` und
die Server-UI rufen dasselbe zentrale Tool mit dem ausgewählten Projekt
als cwd auf, ohne Wrapper oder Installation in jeder Projekt-venv.
Der ältere Option-C-Entwurf in Assist ist kein zweiter Lifecycle-Vertrag.
Der Stack steht in `config/defaults/stack.yaml` (Abschnitt `stack:`). Er wird über ki-core
geladen, Stages und `KI_CFG_*`-Env gelten also auch hier.

`start` startet Dienste im Hintergrund; `run <dienst>` bindet genau einen lokalen
Prozess-Dienst ans Terminal. Beide verwenden dasselbe Kommando, dieselbe Umgebung,
Vorbereitung und Bereitschaftspruefung aus der aufgeloesten Stack-Konfiguration.
Der Vordergrundmodus schreibt ebenfalls nach `var/log/`, laesst sich aus einem
zweiten Terminal mit `stop` beenden und startet keine Abhaengigkeiten automatisch.
Deklarierte Abhaengigkeiten muessen bereits bereit sein. `run` wird fuer
Compose-/External-Dienste und Cluster-Ziele explizit abgelehnt.

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

Maschinenlesbarer Status und Log-Ausschnitte fuer die Assist-Serveransicht:

```bash
stackctl --json status
stackctl --json logs api
stackctl --json projects
```

`start`, `run` und `restart` registrieren den Projektpfad in
`${XDG_STATE_HOME:-~/.local/state}/stackctl/projects.json`. Das ist nur ein
Projektverzeichnis, keine zweite PID-/Dienstkonfiguration. Assist fragt den
tatsaechlichen Status beim zentralen `stackctl` mit dem Projekt als cwd ab und delegiert
Start/Stop/Restart dorthin. Ports, Startkommandos und Secrets werden nicht in
die projektuebergreifende Registry kopiert.

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
[führenden Speichern und Redaktionsgrenzen](../architecture/content-model-matrix.md#0-verbindliche-speicher--und-adaptergrenze-p2).

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

## 📋 SETUP (erste Mal)

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

## 🎯 WICHTIGE URLS

| URL | Beschreibung |
|-----|-------------|
| `http://localhost:8000/` | Startseite |
| `http://localhost:8000/admin/` | Admin Panel |
| `http://localhost:8000/infosite/` | Infosite Dashboard |
| `http://localhost:8000/infosite/projects/` | Projekte |
| `http://localhost:8000/infosite/discover/` | Datei-Entdeckung |

---

## 🔧 VERSCHIEDENE STARTOPTIONEN

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

## 📦 DATENBANK-STRUKTUR

**Pfad:** `~/dev_data/ki-knowledge/django.sqlite3`

**Tabellen:**
- `django_session` - Session-Daten
- `auth_user` - Benutzer
- `auth_group` - Gruppen
- `django_site_infositeproject` - Infosite Projekte
- `django_site_sourcedocument` - Quelldokumente

---

## 🛠️ TROUBLESHOOTING

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

## 💡 TIPPS

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
>>> from ki_knowledge.django_site.models import InfoSiteProject
>>> InfoSiteProject.objects.all()
```

✅ Statische Dateien sammeln:
```bash
python manage.py collectstatic --noinput
```

---

## 🔄 WORKFLOW

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
   http://localhost:8000/infosite/
```

---

## 📝 ENVIRONMENT VARIABLES

Normalerweise nicht nötig – Django-Werte stehen in `ki.yaml` unter
`apps.ki_knowledge.django.*`. Umgebungsvariablen überschreiben sie pro Prozess:

```bash
export DJANGO_DB_PATH=/custom/path/django.sqlite3
export DJANGO_SECRET_KEY=your-secret-key-here
export DJANGO_DEBUG=true
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export KI_CFG_LLM__DEFAULT_PROVIDER=mock   # jeder ki-core-Wert: KI_CFG_<pfad mit __>
```

---

## ✨ Fertig!

Die Django Site ist jetzt ready für Development. Viel Erfolg! 🎉
