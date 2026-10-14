# YAML-Konfiguration: Betrieb und Bedienung

Stand: 2026-10-14, anhand des aktuellen Quellcodes der Arbeitskopien.
Kanonische Quelle: `yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md` im Projekt
**yaml-cfg-wizard** (Paketname mit Bindestrichen, Checkout hier mit Unterstrichen).
Identische Kopien liegen in `ki-knowledge/doc/`, `ia3simworld/doc/`,
`kicli/doc/` und `kicli-code-assist/docs/`. Aenderungen zuerst an der Quelle
pflegen, dann die Kopien aktualisieren.

Dieser Stand beschreibt vorhandenen Code, nicht einen freigegebenen Rollout.
Die neuen Editor-/Identity-Anbindungen sind teilweise uncommitted; Installation,
Integrationstests und produktive Verfuegbarkeit sind hier **nicht nachgewiesen**.
Es wurden fuer diese Dokumentation keine Dienste installiert oder neu gestartet.
Das Konzept und die weitere Entwicklung stehen separat in
`yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md`; historische Auszuege in
`yaml_cfg_wizard/doc/YAML_CONFIG_ARCHIVE.md` (jeweils relativ zum Workspace).

## Zuerst den tatsaechlichen Verbraucher bestimmen

| Projekt | Verbraucher und heutige Bedienung |
| --- | --- |
| yaml-cfg-wizard | `ConfigResolver`, Schema-/CLI-Werkzeuge und neuer skalarer Allowlist-Editor; keine eigenstaendige Web-App und kein Vollbaum-GUI |
| ki-core | `load_config()` verbindet Wizard, KI-Schichten und Schemas; Framework, keine App-Administration |
| ki-knowledge | `AppConfig` nutzt ki-core; Django-Anzeige und begrenzter optionaler Sync-Editor; DB-Overrides separat |
| kicli-code-assist | `AppConfig` nutzt ki-core; eigener Textual-Settings-Dialog, nicht der neue Web-Editor |
| kicli | Eigener alter `kicli/config.py`-Loader; **keine** allgemeine ki-core/Wizard-Schichtenintegration |
| ia3simworld | Go-Dienste nutzen koanf, Launcher eigenes Python; Wizard nur im begrenzten Python-Editor-Adapter |

Eine vorhandene YAML-Datei oder Schema-Definition bedeutet nicht, dass alle
Dienste sie lesen. Insbesondere ia3simworld und kicli nicht nach der ki-core-
Rangfolge administrieren.

## Gemeinsamer Wizard: Schichten, CLI und Installation

`ConfigResolver` merged von niedrig nach hoch: Defaults-Verzeichnis, explizite
Defaults-Dateien, Profil-Verzeichnis/-Dateien, Stage-Verzeichnis/-Dateien,
Runtime-Datei/-Dateien, Environment. Mappings werden rekursiv zusammengefuehrt;
Listen und Skalare ersetzt, nicht angehaengt. Verzeichnisse laden alle `*.yaml`
sortiert, danach alle `*.yml` sortiert. Die Auswahl **eines** Profils/einer Stage
ist Aufgabe des Hosts, nicht automatisch Eigenschaft des Resolvers.
Der generische Resolver kennt weder `ki.yaml` noch `creds.yaml` als Sonderdateien.

Im aktivierten App-Venv, mit benachbarten Checkouts statt festen Host-Pfaden:

```bash
python -m pip install -e '../yaml_cfg_wizard[cli]'
yaml-cfg --help
yaml-cfg config skeleton -o ki.generated.yaml
yaml-cfg config verify ki.generated.yaml schema/app.schema.yaml
yaml-cfg profile list config/profiles
yaml-cfg profile set local --profiles-dir config/profiles
```

`schema/app.schema.yaml` und `local` sind Platzhalter: vorhandenes App-Schema/
Profil einsetzen. Skeleton ohne Schemaargument entdeckt optional das installierte
ki-core-Basisschema und `./schema/*.schema.yaml`; ohne Schema schlaegt es fehl.
Skeleton kann Ausgabedateien ueberschreiben: nicht ungeprueft ueber `ki.yaml`
ausfuehren. Bibliothek: `pip install -e ../yaml_cfg_wizard`;
Django-Adapter: `pip install -e '../yaml_cfg_wizard[django]'`.
`pyproject.toml` nennt 0.2.0 und Python >=3.10; die tatsaechlich installierte
Version und Extras separat pruefen. Die Bibliotheksinstallation allein bringt
Typer fuer die CLI nicht mit.

Explizite Schichtauswahl fuer eine **nicht geheime** Diagnose:

```bash
yaml-cfg config resolve --defaults-dir config/defaults --defaults ki.yaml \
  --profile config/profiles/local.yaml --stage config/stages/dev.yaml \
  --runtime-file config/runtime/runtime.yaml --env-prefix KI_CFG_
```

Nur existierende benoetigte Schichten angeben. `--profile`/`--stage` erwarten
Dateipfade, keine Profilnamen. `--stages-dir` liest alle Stage-Dateien, nicht
`KI_STAGE` oder `.active_stage`. `--profiles-dir` verwendet einen aktiven
`.active_profile`-Marker, andernfalls alle Profil-Dateien. Das ist **nicht**
automatisch dieselbe Aufloesung wie ki-core. Die CLI merged keine Credentials
von selbst. `show`/`list --config ...` lesen nur diese Datei plus Schema-
Defaults, nicht die gesamte App-Aufloesung; `show KEY` nimmt einen Top-Level-Key.

**Validierungsgrenze:** `config verify` prueft eine Datei gegen ein Schema.
`config resolve --schema` fuellt Schema-Defaults auf, validiert damit aber
nicht die volle Config. Sein `--output` schreibt aktuell die Resolver-Schichten
ohne die danach fuer stdout aufgefuellten Schema-Defaults. `ConfigResolver`
validiert nur mit explizitem `schema_file` (Draft 7, dort ohne FormatChecker).
Keine pauschale Zusage vollstaendiger App-/Formatvalidierung ableiten.

## ki-core-Schichten: ki-knowledge und kicli-code-assist

Niedrig nach hoch:

```text
Schema-Skeleton/Defaults
  -> config/defaults/*.yaml (danach *.yml)
  -> ki.yaml
  -> ein aktives Profil
  -> eine aktive Stage
  -> config/runtime/runtime.yaml
  -> KI_CFG_*
  -> creds.yaml
```

Die Schema-Basis ist `ki-core/src/ki_core/schema/config.schema.yaml`.
App-Schemas sind `ki-knowledge/schema/ki_knowledge.schema.yaml` und
`kicli-code-assist/schema/kicli.schema.yaml`; ki-core sucht `schema/*.schema.yaml`
vom Arbeitsverzeichnis aus bis zu fuenf Verzeichnisebenen aufwaerts.
Aus dem Projektroot starten, damit Schema- und Dateisuche zusammenpassen.
Ein flaches `config/defaults.yaml` ist nicht automatisch das Defaults-Verzeichnis.

Hauptdateisuche: vorhandener expliziter Pfad, sonst `./ki.yaml`, sonst
`~/.config/ki/ki.yaml`. Ein nicht existierender expliziter Pfad ist derzeit
kein harter Fehler, sondern faellt auf diese Suche zurueck.
`config/` liegt neben der gefundenen Hauptdatei, ohne Hauptdatei im cwd.
Credentials: bei explizitem Pfad zuerst daneben `creds.yaml`, dann daneben
`config/creds.yaml`; sonst/anschliessend `./creds.yaml`,
`~/.config/ki/creds.yaml`. Nur die erste gefundene Credentials-Datei wird gelesen.

Profil: `KI_PROFILE`, sonst `config/profiles/.active_profile`.
Stage: `KI_STAGE`, sonst `config/stages/.active_stage`.
Geladen wird `<name>.yaml` oder `<name>.yml`; fehlende ausgewaehlte Dateien
erzeugen einen Fehler. Ohne Auswahl wird diese Schicht uebersprungen.
Beispiel fuer ki-knowledge:

```bash
echo dev-lokal > config/stages/.active_stage
KI_CFG_STACK__SERVICES__DJANGO__PORT=8011 ./kistack start
```

Nesting nutzt `__`, z.B. `KI_CFG_LLM__PROVIDERS__OLLAMA__BASE_URL`.
Werte werden zu bool/int/float/null oder String konvertiert. ki-core laedt
zusaetzlich dotenv beim Import; Prozess-Environment und alte `.env`-Dateien
bei unerwarteten Werten mitpruefen, aber keine neue parallele Konfiglinie anlegen.
`creds.yaml` gewinnt auch ueber `KI_CFG_*`: dort keine nicht geheimen
Port-/Stage-Overrides verstecken.
Secrets muessen an den **konsumierten** Pfad, z.B.
`llm.providers.ki.api_key`. Ein zusaetzlicher Wrapper `creds.llm...`
wird nicht automatisch nach `llm...` verschoben.

ki-core validiert die Resolver-Schichten und Credentials separat gegen das
Basisschema und fuellt anschliessend das gemergte Schema-Skeleton auf.
Eine abschliessende Validierung der vollstaendigen Config gegen alle App-Schemas
findet in `load_config()` derzeit nicht statt. Der neue Editor prueft staerker.

### ki-knowledge

Stack-Kommandos: `./kistack install|status|start`, fuer einen erforderlichen
Django-Neustart `./kistack restart django`; weitere Bedienung in `doc/DJANGO_DEV.md`.
Stages: `dev-lokal`, `prod`, `dev-mk`, `prod-k8s`.
Django-Settings wie Ports/Hosts und `DJANGO_*`-Overrides werden teilweise beim
Start gelesen; nach deren Aenderung den betroffenen Dienst neu starten.
Der `AppConfig`-Cache erkennt viele Datei-/`KI_CFG_*`-Aenderungen, ist aber
keine allgemeine Hot-Reload-Garantie (u.a. Selektoren gesondert beachten).

Vorhandener neuer Code: `/settings/config/sync/`, nur aktive Superuser,
GET/CSRF-POST. Optionales App-Extra `.[config-editor]` verlangt
`yaml-cfg-wizard[django]>=0.2.0`. Ohne importierbaren Core/Adapter oder sicheren
projekteigenen Zielpfad bleibt die Seite read-only; POST dann 405.
Installation bei Bedarf im App-Venv:

```bash
python -m pip install -e '../yaml_cfg_wizard[django]'
python -m pip install -e '.[config-editor]'
```

Allowlist: `apps.ki_knowledge.distributed.public_url` und `federation_id`;
Ziel nur `config/runtime/runtime.yaml` unterhalb des cwd, keine Symlinks.
URL ohne Credentials, Query oder Fragment. Setzen speichert einen skalaren
Override; Entfernen stellt Vererbung wieder her. `""` und null sind Werte,
keine Loeschbefehle (das Feldschema entscheidet, ob null erlaubt ist).
Diese beiden Felder werden bei Node-Abfragen frisch gelesen; nach erfolgter
Paket-/Codeinstallation und initialem Neustart brauchen deren YAML-Aenderungen
keinen weiteren Neustart. Env/Credentials koennen den gespeicherten Wert maskieren.

**DB statt YAML:** `/admin-overview/sync/` verwaltet `NodeConfig`.
Bei vorhandenem lokalem Datensatz gewinnt die DB fuer `is_enabled` und
`sync_on_connect`; nichtleere Rolle und Shared Secret ersetzen YAML.
Bei Host-Rolle ersetzt eine nichtleere `base_url` die YAML-`master_url`,
sonst bleibt der YAML-Fallback. Diese Felder sind bewusst nicht im YAML-Editor.
Node-ID, DSN und Secrets werden dort ebenfalls nicht angeboten.
Der YAML-Editor ist nicht die Identity-Administration; Identity-Sync-Code
ist keine Zusage, dass YAML/Passwoerter zwischen Nodes synchronisiert werden.

### kicli-code-assist

Start z.B. `kicli-assist tui`; CLI-Diagnose `kicli-assist doctor`. Die weiteren
CLI-Kommandos sind `tmux`, `chat` und `openinterpreter`
(`kicli_code_assist/cli_commands.yaml`, `pyproject.toml`).
`kicli_code_assist/app_config.py` wickelt `ki_core.load_config()` ab und bildet
`llm.providers`, `http`, `storage` und `apps.kicli` auf typisierte Attribute
ab. Weitere Verbraucher lesen `security` und `prompts` ueber `AppConfig.raw`.

ki-core sucht `ki.yaml` im Arbeitsverzeichnis, danach
`~/.config/ki/ki.yaml`; die Layer liegen im danebenliegenden `config/`.
Prioritaet (hoch nach niedrig): `creds.yaml` -> `KI_CFG_*` (`__` fuer
Verschachtelung) -> `config/runtime/runtime.yaml` -> ausgewaehlte Stage
(`KI_STAGE` oder `config/stages/.active_stage`) -> ausgewaehltes Profil
(`KI_PROFILE` oder `config/profiles/.active_profile`) -> Hauptdatei
`ki.yaml` -> `config/defaults/*.yaml` -> Schema-Defaults. ki-core laedt auch
eine gefundene `.env`; bereits gesetzte Prozessvariablen werden dabei nicht
ueberschrieben.

Der eigene Settings-Dialog (`ui/settings_panel.py`) verwendet das gemergte
ki-core- und App-Schema und schreibt die eingesammelten Werte aller
angezeigten Felder in die von `find_config_path()` ausgewaehlte Hauptdatei
(normalerweise `ki.yaml`), nicht in den Runtime-Layer. Er beschraenkt das
Schreiben nicht auf Felder, die der Benutzer tatsaechlich geaendert hat.
`creds` und `prompts` sind aus dem Dialog ausgeschlossen;
bekannte sensible Blattnamen werden ebenfalls ausgeblendet, das ist aber keine
vollstaendige Secret-Redaktion beliebiger Schemafelder. Hoehere Layer koennen
Dialog-Aenderungen weiter ueberdecken. Speichern aktualisiert weder laufende
Clients noch deren Konfiguration; fuer verlaessliche Uebernahme neu starten.

## kicli: bewusst abweichender Alt-Loader

`kicli/config.py` sucht die erste vorhandene Datei:
`kicli.yaml`, `config.yaml`, `.kicli.yaml`, `config/kicli.yaml`,
`config/config.yaml`, `config/dev.yaml`, `config/prod.yaml`,
`config/minikube.yaml`, `~/.config/kicli/config.yaml`.
Credentials separat: `creds.yaml`, `config/creds.yaml`,
`~/.config/kicli/creds.yaml`. Das alte Format nutzt u.a. `ki` und `ollama`,
nicht automatisch `llm.providers`.

Fuer KI-URL und API-Key prueft der Accessor zuerst die entsprechenden
Credentials-Formen in `creds.yaml`, danach die alten Root-/`ki`-Felder der
gewaehlten Konfigurationsdatei. Modell, Ollama, Jira und HTTP-Timeout kommen
nicht aus `creds.yaml`: dort gelten Konfigurationsdateiwerte vor den lokalen
Code-Defaults. `from_env()` laedt zuerst eine gefundene `.env` ohne bereits
gesetzte Prozessvariablen zu ueberschreiben; anschliessend gewinnen die
spezifischen Env-Variablen
`KI_BASE_URL`, `KI_API_KEY`, `KI_MODEL`, `KI_REQUEST_TIMEOUT`,
`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`.
Kein automatisches `KI_CFG_*`, keine Wizard-Stage-/Runtime-Vererbung und keine
zentrale Schema-Validierung zusagen.
Vorhandene `scripts/select_profile.sh` und `scripts/run_with_profile.sh` sowie
`config/README.md` dokumentieren die lokale Profilbedienung; sie sind kein
Beleg einer ki-core-Migration. Kein neuer Wizard-Webeditor angebunden.
Neue CLI-Prozesse lesen neu; laufende Verbraucher bei Bedarf neu starten.

## ia3simworld: mehrere reale Konfiglinien

Die Dienste haben getrennte Verbraucher. API-Gateway laedt Defaults
`ports.yaml`, `node.yaml`, `auth.yaml`; World-Sim laedt zusaetzlich
`world.yaml` und `ai.yaml`. Beide Go-Dienste wenden in dieser Reihenfolge an:
Defaults -> `PROFILE` -> `STAGE` (`config/stages/<stage>/config.yaml`) ->
`auth.*` aus `config/runtime/runtime.yaml` und danach
`config/runtime/auth.yaml` -> Environment. Die beiden Runtime-Dateien werden
also nur fuer `auth.*` eingemerged; `runtime.yaml` ist kein allgemeiner
Node-/World-Override. Die private `auth.yaml` wird auf Dateirechte geprueft;
`runtime.yaml` darf `auth.internal_secret` und `auth.federation_secret` nicht
enthalten.

Go verwendet `koanf`, nicht `KI_CFG_*`: der allgemeine unpraefixierte
Env-Provider macht Schluessel klein und verwendet **Punkte** als
Verschachtelung (`NODE.MASTER_URL` -> `node.master_url`); Unterstriche oder
`__` werden nicht in Punkte umgewandelt. World-Sim prueft zusaetzlich
`MASTER_URL` direkt als Fallback, wenn `node.master_url` leer ist.
Obwohl es keine speziellen Auth-Env-Aliase gibt, kann der allgemeine Provider
literal gepunktete Schluessel wie `AUTH.INTERNAL_SECRET` auf `auth.*` abbilden.
Auch Defaults, Profil und Stage werden vor diesem Provider geladen; die
Beschraenkung auf private Runtime-Dateien ist daher eine Betriebsregel, keine
vollstaendige Loader-Erzwingung. Machine-Secrets gehoeren nur in die private
`auth.yaml`; nicht in Defaults/Profile/Stages oder Prozess-Environment.

Der Agent-Dienst (`apps/agent-service/config.py`) hat einen anderen Loader:
Defaults `ports/world/ai/node` -> Profildatei -> Stage-Datei ->
Env-Verschachtelung per `__` (z.B. `WORLD__TICK_RATE_MS`, `NODE__ID`).
Er liest keine Go-Runtime-Dateien und hat keinen ki-core-Resolver. Der
Web-Client ist ebenfalls kein YAML-Layer-Consumer: `ia3ctl` gibt ihm
`PROFILE`/`STAGE` sowie `NEXT_PUBLIC_PROFILE`/`NEXT_PUBLIC_STAGE`; die UI
verwendet Profilwerte fuer Anzeige/Profilverhalten und `NEXT_PUBLIC_API_BASE`
fuer die API-Adresse, nicht aber eine Stage-Konfiguration.

`scripts/ia3ctl/runtime_config.py` ist nur der Orchestrierungs-Loader. Er merged
Defaults aus `config/defaults/ports.yaml`, danach `runtime/runtime.yaml`,
`runtime/ia3ctl-runtime.yaml`, das exakt benannte Profil und
`config/stages/<stage>.yaml`; das Ergebnis speist den Service-Katalog und
dessen Abhaengigkeiten. Die aktuellen Stage-Konfigurationen liegen jedoch als
`config/stages/<stage>/config.yaml`, nicht als die von diesem Loader gesuchte
flache Datei, sodass diese Stage-Layer den Katalog derzeit nicht ueberlagern.
`scripts/ia3ctl/ports.py` liest unabhaengig davon **nur**
`config/defaults/ports.yaml`; Launcher-Ports werden nicht durch Profil, Stage
oder Runtime-Overlays ersetzt. Der Launcher verwendet ausserdem nur die
expliziten rohen `--profile`/`--stage`-Argumente (nicht geerbte
Umgebungsselektoren) beim Laden des Katalogs, bevor er Profile fuer die
Kindprozesse normalisiert.

Alias-Namen (`small`, `medium`, `default`, `standard`, `large`, `perf`) sind
zwar in der CLI-/Go-/Editor-Logik vorhanden, werden aber nicht von allen
Verbrauchern gleich behandelt. Insbesondere sucht der Orchestrierungs-Loader
vor der CLI-Normalisierung nach `profiles/<Argument>.yaml`: Aliase ohne
gleichnamige Datei koennen daher schon beim Katalog-Laden scheitern; `standard`
laedt dort `standard.yaml`, waehrend die Kindprozesse `medium-standard`
erhalten. Fuer konsistente Starts die Dateinamen `small-test`,
`medium-standard`, `large-federated` oder `perf-benchmark` verwenden.

```bash
python scripts/ia3ctl.py dev-lokal-start 1 --services agent,sim,api,web --profile small-test
python scripts/ia3ctl.py dev-lokal-status
```

Weitere reale CLI-Kommandos sind `dev-lokal-stop`, `dev-lokal-diagnose`,
`dev-lokal-build-status`, `dev-lokal-clean-web-cache`, `dev-mk-start|stop|status`
und `prod-mk-start|stop|status`; clusterbezogene Konfiguration nicht mit
ki-knowledge-`kistack` gleichsetzen. Die Dienste laden ihre jeweilige
Startup-Konfiguration beim Start; Editor-Speichern startet/reloaded/deployed
keine Dienste.
`state/domain_settings.json` und andere Simulationsdaten sind separate
Runtime-Zustaende, keine generische Wizard-Konfigschicht.

### Begrenzter neuer Editor und Auth-Grenze

Der IA3-Adapter liegt wieder als eigenstaendige Distribution
`ia3-config-editor` in `packages/ia3-config-editor` und exportiert
`ia3_config_editor.create_editor`. Er verlangt `yaml-cfg-wizard>=0.2.0`
und `PyYAML>=6`. Das neue Geschwister-Repository `yaml_cfg_wizard_ui`
enthaelt die generische Distribution `yaml-cfg-wizard-ui` und
`yaml_cfg_wizard_ui.render_page`: paketierte HTML/CSS/Vanilla-JS-Ressourcen,
keine IA3-Factories und keine Core-/Django-/React-Laufzeitabhaengigkeit.
Die React-Oberflaeche bettet die authentifizierte gleichnamige Gateway-Seite
`GET /api/admin/config-editor/ui` per Same-Origin-Iframe ein. Der Renderer
erhaelt die aktuelle Session-CSRF als sicher escaptes JSON und explizite
String-Metadaten. Keine beliebigen Konfigurationsbaeume werden geladen.
Bestehende Venvs muessen beide Pakete installieren; Quellcode ist kein
Nachweis einer aktualisierten Installation.

Die Extraktion erweitert weder IA3-Feldumfang noch unterstuetzte Hosts.
Das `_SCHEMA` im Adapter beschreibt nur `node.master_url`
(String, max. 2048 Zeichen), kein vollstaendiges Schema aller Go-Settings.
Editierbar ist das Feld in `config/defaults/node.yaml` oder im ausgewaehlten
Profil. Der Adapter durchsucht Defaults `ports`, `world`, `ai`, `node` und
danach das Profil, wendet den literal gepunkteten `NODE.MASTER_URL`-Override
und als Fallback `MASTER_URL` an. `STAGE` wird abgelehnt; Runtime/auth-Dateien
und Secrets sind nicht editierbar. Offline-Nutzung erfolgt ueber die Python-API,
ohne eigenes CLI- oder `python -m`-Bedienkommando.

Die aktuelle Gateway-Anbindung hat `GET/POST /api/admin/config-editor`;
sie verlangt lokale Admin-Session, Admin-Rolle und Transportpruefung,
bei POST ausserdem exaktes CSRF und JSON. Standard ist geschlossen.
`IA3_CONFIG_EDITOR_SHARED_STARTUP=1` ist nur eine explizite Betreiberzusage,
**kein Nachweis**: Gateway und World-Sim muessen denselben Configbaum und
identische `PROFILE`/`STAGE`/Master-URL-Overrides konsumieren.
Der Bridge-Prozess erwartet fest `venv/bin/python3` im Projektroot und isolierte
Imports. Paket-Setup dort, wenn diese Integration gezielt eingerichtet wird:

```bash
python3 -m venv venv
venv/bin/pip install ../yaml_cfg_wizard ../yaml_cfg_wizard_ui ./packages/ia3-config-editor
venv/bin/python3 -I -c 'from ia3_config_editor import create_editor; from yaml_cfg_wizard_ui import render_page'
```

Das prueft nur Imports, nicht sicheren Betrieb. Keine automatisch vorhandene
Admin-Identitaet annehmen: Auth-Provisionierung/Bootstrap und HTTPS nach
`doc/local-admin-auth.md` einrichten. HTTP ist nur bei expliziter
Local-HTTP-Freigabe mit exaktem Loopback-Origin, Host und TCP-Peer zulaessig.
TLS-terminierender Ingress/Forwarded-Header oder Cross-Site-Frontend sind ohne
separates Trusted-Proxy-Konzept **nicht unterstuetzt**. Nicht durch Auth-Abschalten
oder oeffentliches HTTP umgehen. Erst nach sicherem Setup testen; aktuell
kein verifizierter Produktions-Rollout.

Identity-Sync ist getrennt: Wenn aktiviert, sendet das Gateway einen Snapshot
mit genau dem aktuellen lokalen Gateway-Benutzer an
`/knowledge/sync/identities/`. `identity-outbox.json` wird vor jedem POST
geschrieben/ersetzt; der erste Versuch erfolgt sofort, danach wiederholt ein
60-Sekunden-Ticker den Snapshot. Das ist keine Ereignis-Retryqueue.
`identity-status.json` dokumentiert den letzten Status/Fehler. Das ist weder
YAML-Federation noch garantiert vollstaendige Offline-Konvergenz.
Worker mit Master-URL brauchen ein getrenntes Federation-Secret; keine Secrets
in diesen Guide, Editorseiten, Commit oder Support-Ausgaben uebernehmen.

## Sicher speichern und Fehler eingrenzen

Vor Aenderungen geschuetzte Sicherung der Ziel-Datei erstellen (nicht in Git);
Ziel, Verbraucher, hoehere Schichten und Restart-Bedarf feststellen.
Secrets-Dateien ignorieren lassen, restriktive Rechte (typisch `0600`) und
geschuetzte Verzeichnisse nutzen. `show`, `resolve`, `env show`, Schemafehler
und Stack-Diagnosen sind **nicht pauschal redigiert**; keine Komplettausgaben
mit echten Credentials in Logs, Tickets oder Chats kopieren.

Der neue Editor zeigt nur registrierte skalare Pfade, Override und effektiven
Wert, keine vollstaendige Herkunftskette. Er validiert die neu aufgeloeste
Config und die geaenderten Feldwerte, verwendet SHA-256-Dateirevision,
Unix-Advisory-Lock und atomaren Dateitausch. Konflikt: neu laden und Aenderung
erneut pruefen, nicht blind ueberschreiben. Externe Schreiber muessen das
persistente `.editor.lock` beachten; die Revision erfasst nicht Aenderungen
anderer Schichten. Kommentare/Formatierung werden beim Speichern nicht erhalten.
Neue Dateien `0600`, bestehende Berechtigungen bleiben bestehen; Symlinks sind
verboten. Der Host verantwortet Autorisierung, Allowlist und sichere Verzeichnisse.

Bei unwirksamen Werten zuerst die echte Rangfolge inklusive DB/Env/Credentials
pruefen, dann cwd, Selektoren und Zielpfad, danach den erforderlichen Neustart.
Es gibt derzeit keine universelle GUI fuer den ganzen Konfigbaum, keine
einheitliche Go-/Python-Aufloesung und keinen allgemeinen Live-Reload.
