# 🚀 Django Dev - Quick Start Guide

## ⚡ SCHNELLSTART

```bash
# Option 1: EMPFOHLEN - Ein Befehl mit Migrations
python examples/run_knowledge_django.py

# Option 2: Manuell
python manage.py migrate
python manage.py runserver
```

Nach Start: **http://localhost:8000**

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

Optional, für Anpassungen:

```bash
# Database Pfad
export DJANGO_DB_PATH=/custom/path/django.sqlite3

# Secret Key (WICHTIG für Production!)
export DJANGO_SECRET_KEY=your-secret-key-here

# Debug Mode
export DJANGO_DEBUG=true

# Allowed Hosts
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## ✨ Fertig!

Die Django Site ist jetzt ready für Development. Viel Erfolg! 🎉
