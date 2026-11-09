---
project: ki-knowledge
agent_project: ki-knowledge
scope: guides
created: "2026-09-02 18"
updated: "2026-11-07 23"
update_reason: "Abschnitte gekennzeichnet und CLI-Aussagen am Code abgeglichen"
status: active
semantic_blocks:
  - features
  - installation
  - usage
  - configuration
  - architecture
  - extension
  - dynamic-architecture
  - debugging
  - examples
  - tests
  - references
---

# Ki-Knowledge CLI

Robuste Click-basierte CLI mit **dynamischer YAML-Konfiguration** für die Infosite-Verwaltung und andere Funktionen.

Die Standard-Kommandohierarchie liegt in `ki_knowledge/cli/cli.yaml` und wird
mitinstalliert. Eine eigene `cli.yaml` im Arbeitsverzeichnis ersetzt diese
Defaults; fehlerhafte Overrides werden mit Pfad gemeldet, nicht ignoriert.
Details zum [Paket-Build](packaging.md).

<a id="features"></a>
## Features [features]

Die Kommandohierarchie ist in YAML konfigurierbar und unterstützt Gruppen.
Angegebene Python-Callbacks werden importiert; neue Funktionalität benötigt
eine entsprechende Implementierung.

<a id="installation"></a>
## Installation [installation]

Die CLI ist bereits im Projekt integriert:

```bash
cd ki-knowledge
source .venv/bin/activate
```

<a id="verwendung"></a>
<a id="usage"></a>
## Verwendung [usage]

### Help anzeigen

```bash
python -m ki_knowledge.cli.main --help
python -m ki_knowledge.cli.main infosite --help
python -m ki_knowledge.cli.main infosite generate --help
```

### Infosite generieren

```bash
python -m ki_knowledge.cli.main infosite generate
```

Erfordert `ki.yaml` Konfiguration:
```yaml
infosite:
  enabled: true
  title: "My Knowledge Base"
  domain: "default"
  output_base_dir: "/path/to/output"
```

### Verfügbare Kommandos

**Infosite Management:**
```bash
kictl infosite init       # Dialog; legt derzeit kein Projekt an
kictl infosite generate   # Infosite generieren
kictl infosite list       # Projekte auflisten (mit Django)
kictl infosite discover   # Verzeichnis interaktiv einlesen
```

**Nextcloud (WebDAV, siehe [NEXTCLOUD.md](../integration/NEXTCLOUD.md)):**
```bash
kictl nextcloud status                         # Konfig (Passwort maskiert), kein Netz
kictl nextcloud list -d <domain> [ordner]      # Eingangsordner auflisten
kictl nextcloud download -d <domain> <datei>   # in den lokalen Eingangs-Cache
kictl nextcloud import -d <domain> <datei.md>  # Markdown importieren (--all: Ordner)
kictl nextcloud upload -d <domain> <ausgabe>   # erzeugte Datei hochladen, nie überschreiben
```

**Knowledge Base:** Die folgenden Einträge sind aktuell Platzhalter ohne
fachlichen Callback. Sie geben lediglich den Kommandonamen aus:
```bash
kictl knowledge import
kictl knowledge search
kictl knowledge graph
```

<a id="konfiguration"></a>
<a id="configuration"></a>
## Konfiguration [configuration]

Die CLI-Hierarchie ist in `ki_knowledge/cli/cli.yaml` definiert. Fuer lokale
Anpassungen kann eine eigene `cli.yaml` im Arbeitsverzeichnis liegen:

```yaml
cli:
  commands:
    # Kommando-Gruppe
    infosite:
      help: "Knowledge Presentation Management"
      commands:
        # Unterkommando
        generate:
          help: "Generate infosite from documents"
          callback: "ki_knowledge.cli.commands.infosite:generate_infosite"
        
        # Weiterer Callback
        init:
          help: "Initialize new project"
          callback: "ki_knowledge.cli.commands.infosite:init_project"

    # Weitere Gruppen...
    knowledge:
      help: "Knowledge Base Management"
      commands:
        import:
          help: "Import documents"
        search:
          help: "Search knowledge base"
```

### Callback-Format

Der `callback` verweist auf ein Python-Callable im Format `module:function`:

```
"ki_knowledge.cli.commands.infosite:generate_infosite"
         ↓                                    ↓
    Modul-Pfad                       Funktionsname
```

Die Funktion wird automatisch importiert und aufgerufen.

<a id="architektur"></a>
<a id="architecture"></a>
## Architektur [architecture]

### CLI Framework (`framework.py`)

Kernkomponenten:

- **`CLICommandSpec`** - Spezifikation für ein Kommando oder eine Gruppe
- **`CLIBuilder`** - Erzeugt Click-CLI aus YAML-Config
- **`build_cli_from_config()`** - Haupt-Einstiegspunkt

### Kommando-Module

Konkrete Kommandos in `ki_knowledge/cli/commands/`:

- **`infosite.py`** - Infosite-Management
  - `init_project()` - Initialisierungsdialog ohne persistente Projektanlage
  - `generate_infosite()` - Generation
  - `list_projects()` - Auflistung (optional Django)
  - `discover_documents()` - Dokument-Scanning

<a id="erweiterung"></a>
<a id="extension"></a>
## Erweiterung [extension]

### Neue Kommando-Gruppe hinzufügen

1. **Modul erstellen** (`ki_knowledge/cli/commands/myfeature.py`):

```python
import click

def my_command():
    """My command description."""
    click.echo("Hello from my command!")
```

2. **In `ki_knowledge/cli/cli.yaml` eintragen** (oder im lokalen Override):

```yaml
cli:
  commands:
    myfeature:
      help: "My Feature"
      commands:
        cmd:
          help: "My command"
          callback: "ki_knowledge.cli.commands.myfeature:my_command"
```

3. **Testen**:

```bash
python -m ki_knowledge.cli.main myfeature cmd
```

### Neue Kommandos mit Parametern

Ein einfacher Callback kann beispielsweise interaktiv nach Eingaben fragen.
Für echte Click-Optionen und Argumente ist ein entsprechend definiertes
Click-Command erforderlich.

```python
import click

def my_command_with_args():
    """Command that prompts for input."""
    name = click.prompt("Your name")
    click.echo(f"Hello, {name}!")
```

<a id="vorteile-der-dynamischen-architektur"></a>
<a id="dynamic-architecture"></a>
## Vorteile der dynamischen Architektur [dynamic-architecture]

Die YAML-Datei legt die verschachtelte Struktur fest und verweist auf die
Callbacks. Sie kann vorhandene Funktionen neu kombinieren, implementiert aber
keine neuen Funktionen selbst.

<a id="debugging"></a>
## Debugging [debugging]

### Config validieren

```bash
python -c "
from pathlib import Path
from ki_knowledge.cli.framework import CLIBuilder
builder = CLIBuilder.from_yaml_file(Path('ki_knowledge/cli/cli.yaml'))
cli = builder.build_cli()
print('CLI loaded successfully')
print('Commands:', list(cli.commands.keys()))
"
```

### Einzelne Funktionen testen

```python
from ki_knowledge.cli.commands.infosite import generate_infosite
generate_infosite()  # Ruft die Funktion direkt auf
```

<a id="beispiele"></a>
<a id="examples"></a>
## Beispiele [examples]

### Infosite mit CLI generieren

```bash
# Vorhandene Konfiguration prüfen und Werte für infosite.title,
# infosite.domain und infosite.output_base_dir bei Bedarf setzen.
# Danach generieren:
python -m ki_knowledge.cli.main infosite generate
```

Die CLI verwendet `<knowledge.data_root>/documents`, wenn dieses Verzeichnis
existiert; andernfalls erzeugt sie Standardseiten. Das ist nicht automatisch
gleichbedeutend mit der aktuellen Data-Sources- oder Textwerkstatt-Pipeline.

### Neue Kommandogruppe hinzufügen

Siehe "Erweiterung" oben.

<a id="tests"></a>
## Tests [tests]

```bash
pytest tests/test_cli.py -v
```

Test-Abdeckung:
- CLI-Spezifikations-Erstellung
- YAML-Konfiguration laden
- Kommando-Hierarchie-Aufbau
- Callback-Laden
- Kommando-Ausführung

<a id="referenzen"></a>
<a id="references"></a>
## Referenzen [references]

- Click Dokumentation: https://click.palletsprojects.com/
- YAML Format: https://yaml.org/
- Python importlib: https://docs.python.org/3/library/importlib.html
