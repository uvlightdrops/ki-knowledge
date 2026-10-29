# Click CLI vs Django Web Interface

## 🎯 CLICK CLI - Command Line Interface

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
- Keine Code-Änderungen nötig für neue Kommandos

---

## 🌐 DJANGO WEB - Web Interface

### Starten:
```bash
stackctl run django
# Alternativer Port über dieselbe Stack-Konfiguration:
KI_CFG_STACK__SERVICES__DJANGO__PORT=8001 stackctl run django
```

### Öffnen in Browser:
- Admin: http://localhost:8000/admin/
- Dashboard: http://localhost:8000/infosite/
- Projekte: http://localhost:8000/infosite/projects/

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

## ⚙️ VERGLEICH

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

## 🚀 QUICK COMMANDS

### CLI - Nur Terminal
```bash
# Neue Infosite generieren
python -m ki_knowledge.cli.main infosite generate

# Quelldokumente entdecken
python -m ki_knowledge.cli.main infosite discover

# Projekte auflisten
python -m ki_knowledge.cli.main infosite list

# Neues Projekt initialisieren
python -m ki_knowledge.cli.main infosite init
```

### Django - Web Browser + Terminal
```bash
# Server starten
stackctl run django

# Dann Browser öffnen:
# http://localhost:8000/admin/
# http://localhost:8000/infosite/
```

---

## 💡 EMPFEHLUNG

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
