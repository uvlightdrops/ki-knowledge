# Ki-Knowledge CLI

Robuste Click-basierte CLI mit **dynamischer YAML-Konfiguration** für die Infosite-Verwaltung und andere Funktionen.

## Features

✨ **Dynamische Hierarchie** - Kommando-Struktur aus `cli.yaml` konfigurierbar  
📦 **Auto-Discovery** - Findet Callbacks automatisch aus Python-Modulen  
🎨 **Strukturiert** - Haupt-Kommandos und Untergruppen  
🔧 **Erweiterbar** - Neue Kommandos einfach in YAML hinzufügen  
⚡ **Schnell** - Click-basierte native CLI  

## Installation

Die CLI ist bereits im Projekt integriert:

```bash
cd ki-knowledge
source .venv/bin/activate
```

## Verwendung

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
ki infosite init           # Neues Projekt initialisieren
ki infosite generate       # Infosite aus Dokumenten generieren
ki infosite list          # Projekte auflisten (mit Django)
ki infosite discover      # Dokumentquellen scannen
```

**Knowledge Base:**
```bash
ki knowledge import       # Dokumente importieren
ki knowledge search       # Knowledge Base durchsuchen
ki knowledge graph        # Knowledge-Graph visualisieren
```

## Konfiguration

Die CLI-Hierarchie ist in `cli.yaml` definiert und kann jederzeit angepasst werden:

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
        
        # Oberflächliches Kommando (ohne Callback)
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

## Architektur

### CLI Framework (`framework.py`)

Kernkomponenten:

- **`CLICommandSpec`** - Spezifikation für ein Kommando oder eine Gruppe
- **`CLIBuilder`** - Erzeugt Click-CLI aus YAML-Config
- **`build_cli_from_config()`** - Haupt-Einstiegspunkt

### Kommando-Module

Konkrete Kommandos in `ki_knowledge/cli/commands/`:

- **`infosite.py`** - Infosite-Management
  - `init_project()` - Neues Projekt
  - `generate_infosite()` - Generation
  - `list_projects()` - Auflistung (optional Django)
  - `discover_documents()` - Dokument-Scanning

## Erweiterung

### Neue Kommando-Gruppe hinzufügen

1. **Modul erstellen** (`ki_knowledge/cli/commands/myfeature.py`):

```python
import click

def my_command():
    """My command description."""
    click.echo("Hello from my command!")
```

2. **In `cli.yaml` eintragen**:

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

Click-Parameter funktionieren automatisch:

```python
import click

def my_command_with_args():
    """Command that prompts for input."""
    name = click.prompt("Your name")
    click.echo(f"Hello, {name}!")
```

## Vorteile der dynamischen Architektur

✅ **Konfigurierbar** - Struktur ändern ohne Code-Modifizierung  
✅ **Wartbar** - YAML ist einfach zu verstehen  
✅ **Skalierbar** - Beliebig viele Kommandos/Gruppen  
✅ **Hierarchisch** - Verschachtelte Kommando-Strukturen  
✅ **Auto-Discovery** - Callbacks werden automatisch geladen  

## Debugging

### Config validieren

```bash
python -c "
from pathlib import Path
from ki_knowledge.cli.framework import CLIBuilder
builder = CLIBuilder.from_yaml_file(Path('cli.yaml'))
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

## Beispiele

### Infosite mit CLI generieren

```bash
# 1. Config vorbereiten
cat > ki.yaml << 'EOF'
infosite:
  enabled: true
  title: "My Knowledge"
  domain: "docs"
  output_base_dir: "./output"
EOF

# 2. Generieren
python -m ki_knowledge.cli.main infosite generate

# 3. Ergebnis prüfen
ls -la output/docs/my-knowledge/
```

### Neue Kommandogruppe hinzufügen

Siehe "Erweiterung" oben.

## Tests

```bash
pytest tests/test_cli.py -v
```

Test-Abdeckung:
- CLI-Spezifikations-Erstellung
- YAML-Konfiguration laden
- Kommando-Hierarchie-Aufbau
- Callback-Laden
- Kommando-Ausführung

## Referenzen

- Click Dokumentation: https://click.palletsprojects.com/
- YAML Format: https://yaml.org/
- Python importlib: https://docs.python.org/3/library/importlib.html
