---
project: ki-knowledge
agent_project: ki-knowledge
scope: guides
created: "2026-09-02 18"
updated: "2026-11-07 23"
update_reason: "Abschnitte gekennzeichnet und veraltete Einstiegspfade korrigiert"
status: active
semantic_blocks:
  - cli-interface
  - django-interface
  - interface-comparison
  - quick-commands
  - recommendations
---

# Click CLI vs Django Web Interface

> Dieser Vergleich ist ein älterer Überblick, keine vollständige
> Funktionsprüfung. Aktuelle Details stehen in der [CLI-Anleitung](CLI.md)
> und der [Textwerkstatt-Anleitung](text-workbench.md).

<a id="click-cli---command-line-interface"></a>
<a id="cli-interface"></a>
## Click CLI - Command Line Interface [cli-interface]

### Starten:
```bash
python -m ki_knowledge.cli.main --help
python -m ki_knowledge.cli.main infosite generate
python -m ki_knowledge.cli.main infosite list
python -m ki_knowledge.cli.main infosite discover
```

### Verwenden für:
✅ Automatisierung & Scripts
✅ Batch-Verarbeitung
✅ CI/CD Pipelines
✅ Schnelle Kommando-Ausführung
✅ Programmtische Integration
✅ Terminal-Workflows

### Konfiguration:
- `ki_knowledge/cli/cli.yaml` - Mitinstallierte Standard-Kommandohierarchie
- `cli.yaml` im Arbeitsverzeichnis - Optionaler lokaler Override
- Vollständig YAML-basiert & veränderbar
- YAML kann vorhandene Callbacks einbinden; neue Funktionalität benötigt
  eine entsprechende Implementierung.

---

<a id="django-web---web-interface"></a>
<a id="django-interface"></a>
## Django Web - Web Interface [django-interface]

### Starten:
```bash
stackctl run django
# Alternativer Port über dieselbe Stack-Konfiguration:
KI_CFG_STACK__SERVICES__DJANGO__PORT=8001 stackctl run django
```

### Öffnen in Browser:
- Admin: http://localhost:8000/admin/
- Dashboard: http://localhost:8000/
- InfoSite-Projekte: http://localhost:8000/output/infosite/
- Textwerkstatt: http://localhost:8000/knowledge/workbench/

### Verwenden für:
✅ Benutzer-freundliche GUI
✅ Projekt-Management
✅ Datei-Uploads
✅ Visuelle Navigation
✅ Team-Zusammenarbeit
✅ Admin-Interface

### Konfiguration:
- `ki_knowledge/django_site/settings.py`
- URL-Routing in `ki_knowledge/django_site/urls.py`
- Admin Models in `ki_knowledge/django_site/infosite_admin.py`

---

<a id="vergleich"></a>
<a id="interface-comparison"></a>
## Vergleich [interface-comparison]

Die folgende Bewertung ist eine subjektive historische Einschätzung, kein
aktueller Funktionsvergleich.

| Feature | CLI | Django Web |
|---------|-----|-----------|
| **Start** | 1 Befehl | 1 Befehl |
| **Lernenswert** | Mittel | Höher (GUI kennenlernen) |
| **Automatisierung** | ⭐⭐⭐ | ⭐ |
| **Benutzerfreundlich** | ⭐ | ⭐⭐⭐ |
| **Skriptbar** | ⭐⭐⭐ | ⭐⭐ |
| **Schnell** | ⭐⭐⭐ | ⭐⭐ |
| **Konfigurierbar** | ⭐⭐⭐ | ⭐⭐ |

---

<a id="quick-commands"></a>
## Quick Commands [quick-commands]

### CLI - Nur Terminal
```bash
# Neue Infosite generieren
python -m ki_knowledge.cli.main infosite generate

# Quelldokumente entdecken
python -m ki_knowledge.cli.main infosite discover

# Projekte auflisten
python -m ki_knowledge.cli.main infosite list

# Initialisierungsdialog anzeigen (legt derzeit kein Projekt an)
python -m ki_knowledge.cli.main infosite init
```

### Django - Web Browser + Terminal
```bash
# Server starten
stackctl run django

# Dann Browser öffnen:
# http://localhost:8000/admin/
# http://localhost:8000/
```

---

<a id="empfehlung"></a>
<a id="recommendations"></a>
## Empfehlung [recommendations]

Historische Orientierung; die tatsächliche Abdeckung der beiden Oberflächen
ist nicht vollständig verglichen.

**Für Anfang:** Django Web Interface
- Leichter zu verstehen
- Visuelles Feedback
- Projekt-Management im Browser

**Für Automation:** Click CLI
- Scripts schreiben
- Batch-Jobs
- Integration in andere Tools

**Optimal:** BEIDE zusammen verwenden!
- Entwicklung im CLI (schnell)
- Verwaltung im Web UI (komfortabel)
