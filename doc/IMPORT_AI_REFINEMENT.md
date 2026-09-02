# 📥 Import & AI Refinement - Django Site Feature

## Overview

Der Django Site wurde um zwei mächtige Features erweitert:

1. **Import Control Panel** - Verzeichnis scannen und Dateien selektiv importieren
2. **AI Refinement Interface** - Markdown-Dateien mit KI verbessern (Struktur, Inhalt, Zusammenfassung)

---

## 🎯 Features

### 1. Import Control (`/infosite/project/<id>/import/`)

**Was es tut:**
- Scannt das konfigurierte Source-Verzeichnis
- Zeigt alle unterstützten Dateien (PDF, Markdown, Text)
- Lässt Sie Dateien selektiv importieren
- Verwaltet Import-Status für jede Datei

**Workflow:**
1. Navigiere zu "Import Control" im Projekt-Dashboard
2. Sehe alle verfügbaren Dateien im Source-Verzeichnis
3. Wähle die Dateien aus, die du importieren möchtest
4. Klick "Import Selected Files"
5. Dateien werden in die SourceDocument-Tabelle übernommen

**Screenshot-UI:**
- Dateiliste mit Checkboxen
- Datei-Typ Badge (PDF, Markdown, Text)
- Datei-Größe
- Import-Status (Pending/Imported)
- "Select All" Checkbox
- Counter für ausgewählte Dateien

---

### 2. AI Refinement (`/infosite/project/<id>/refine/`)

**Was es tut:**
- Zeigt alle generierten Markdown-Dateien
- Bietet 4 Refinement-Modi:
  - **Improve Content** - Bessere Qualität und Klarheit
  - **Restructure** - Bessere Organisation und Hierarchie
  - **Summarize** - Prägnante Zusammenfassungen
  - **All Refinements** - Alle drei kombiniert
- Wendet KI-Verbesserungen auf Dateien an
- Speichert verfeinerte Versionen zurück

**Workflow:**
1. Generiere zunächst Infosite (damit Markdown-Dateien existieren)
2. Navigiere zu "AI Refinement"
3. Wähle die Dateien aus, die verfeinert werden sollen
4. Wähle den Refinement-Modus aus
5. Klick "Apply AI Refinements"
6. KI verbessert die Inhalte und speichert sie

**Refinement-Modi:**
- **Improve**: Verbessert Text-Qualität, Klarheit, Grammatik
- **Structure**: Reorganisiert Inhalte für bessere Lesbarkeit
- **Summarize**: Erstellt kurze, prägnante Zusammenfassungen
- **All**: Wendet alle drei Methoden an

---

## 🛠️ Technische Details

### Views (in `infosite_views.py`)

#### Import Control
```python
@login_required
def infosite_import_control(request, project_id):
    # Zeige alle Dateien im Source-Verzeichnis
    # Markiere bereits importierte
    # Render Import-Control Template
```

#### Import Selected
```python
@login_required
@require_http_methods(["POST"])
def infosite_import_selected(request, project_id):
    # Verarbeite POST mit ausgewählten Dateien
    # Erstelle/Update SourceDocument Einträge
    # Setze imported=True für neue Dateien
```

#### AI Refinement
```python
@login_required
def infosite_ai_refine(request, project_id):
    # Lade alle generierten Markdown-Dateien
    # Zeige Vorschau und Statistiken
    # Render Refinement-Interface
```

#### AI Refinement Apply
```python
@login_required
@require_http_methods(["POST"])
def infosite_ai_refine_apply(request, project_id):
    # Hole ausgewählte Dateien und Refinement-Modus
    # Rufe ki-core AIClient auf
    # Speichere verfeinerte Versionen
```

### URLs (in `infosite_urls.py`)

```
/project/<id>/import/           - Import Control Panel
/project/<id>/import/selected/  - POST: Import ausgewählte Dateien
/project/<id>/refine/           - AI Refinement Interface
/project/<id>/refine/apply/     - POST: Anwende KI-Verbesserungen
```

### Templates

#### `import_control.html`
- Dateiliste mit Checkboxen
- Datei-Typ, Größe, Import-Status
- "Select All" Functionality
- Counter für ausgewählte Dateien
- JavaScript für Client-Side Interaktion

#### `ai_refine.html`
- Refinement-Modus Selector
- Markdown-Datei-Liste mit Vorschau
- Zeige Zeilenzahl pro Datei
- Backup-Warnung vor AI-Anwendung
- File Selection mit Counter

#### `base.html`
- Konsistentes Styling für alle Infosite-Views
- Bootstrap 5 basiert
- Navigation mit Links
- Responsive Design

---

## 🚀 Quick Start

### 1. Server starten
```bash
kictl dev django start
```

### 2. Admin-Benutzer erstellen (falls nicht vorhanden)
```bash
kictl dev django createsuperuser
```

### 3. Projekt erstellen
```bash
# Öffne http://localhost:8000/admin/
# Navigiere zu "Infosite Projects"
# Erstelle neues Projekt mit:
#   - Title: "Mein Projekt"
#   - Domain: "mein-projekt"
#   - Source Directory: /pfad/zu/dokumenten
#   - Enabled: True
```

### 4. Dateien importieren
```bash
# Öffne http://localhost:8000/infosite/project/1/import/
# Wähle Dateien aus
# Klick "Import Selected Files"
```

### 5. Infosite generieren
```bash
# Öffne http://localhost:8000/infosite/project/1/
# Klick "Generate Infosite"
```

### 6. Mit KI verfeinern
```bash
# Öffne http://localhost:8000/infosite/project/1/refine/
# Wähle Markdown-Dateien aus
# Wähle Refinement-Modus (empfohlen: "All Refinements")
# Klick "Apply AI Refinements"
```

---

## 🔐 Permissions

Alle Views sind `@login_required`:
- Nur authentifizierte Benutzer können Import/Refinement durchführen
- Import-Funktion benötigt `django_site.add_infositeproject` Permission
- Generate benötigt `django_site.change_infositeproject` Permission

---

## 🤖 AI Integration

Die KI-Verbesserung nutzt `ki-core`'s AIClient:

```python
from ki_core.client import AIClient
from ki_core.config import Config

config = Config.from_yaml()
client = AIClient(config)
response = client.complete(prompt)
```

**Anforderung:** `ki-core` muss mit aktiviertem AI-Provider konfiguriert sein (z.B. OpenAI, Anthropic, etc.)

---

## ⚠️ Wichtige Hinweise

1. **Backup vor Refinement**: KI-Verbesserungen überschreiben originale Markdown-Dateien
2. **AI-Kosten**: Jede Refinement-Operation verursacht API-Aufrufe zum AI-Provider
3. **Performance**: Bei vielen Dateien kann die Verarbeitung länger dauern
4. **Qualität**: AI-Output sollte vor Veröffentlichung überprüft werden

---

## 📝 Datei-Änderungen

### Neue Dateien
- `ki_knowledge/django_site/templates/infosite/import_control.html`
- `ki_knowledge/django_site/templates/infosite/ai_refine.html`
- `ki_knowledge/django_site/templates/infosite/base.html`

### Modifizierte Dateien
- `ki_knowledge/django_site/infosite_views.py` - 4 neue Views
- `ki_knowledge/django_site/infosite_urls.py` - 4 neue URL-Patterns
- `ki_knowledge/django_site/templates/infosite/dashboard.html` - Base-Template aktualisiert
- `ki_knowledge/django_site/templates/infosite/project_detail.html` - New Action-Buttons

---

## 🎨 UI Features

✅ **Intuitive Interface**
✅ **Real-time Feedback** (Messages, Badges)
✅ **Bulk Selection** (Select All, Checkboxes)
✅ **File Preview** (für AI Refinement)
✅ **Status Indicators** (Imported/Pending/etc)
✅ **Responsive Design** (Bootstrap 5)
✅ **Error Handling** (User-freundliche Fehlermeldungen)

---

## 🔧 Konfiguration

Die meisten Funktionen arbeiten mit bestehender Konfiguration:

```yaml
# ki.yaml
infosite:
  enabled: true
  title: "Mein Infosite"
  domain: "mein-infosite"
  output_base_dir: /path/to/output
```

---

## 📚 Weitere Ressourcen

- `doc/DJANGO_DEV.md` - Django Development Guide
- `doc/INFOSITE.md` - Infosite Feature Guide
- `doc/knowledge_presentation_requirements.md` - Full Requirements

---

**Status: ✅ FERTIG & GETESTET**

Alle Features sind implementiert und ready für Production! 🎉
