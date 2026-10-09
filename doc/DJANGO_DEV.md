# 🚀 Django Dev - Quick Start Guide

## ⚡ SCHNELLSTART

```bash
# Option 1: EMPFOHLEN - ganzer Stack (Postgres, Ollama-Check, API :8090, Django :8000)
./kistack start          # startet nur, was noch nicht läuft (Django: migrate + runserver)
./kistack status         # was läuft, PIDs, URLs
./kistack stop           # API + Django stoppen (Postgres/Ollama bleiben)
./kistack restart django # einzelne Dienste: postgres | ollama | api | django
./kistack logs django -f # Logs unter var/log/, PIDs unter var/run/
./kistack install        # .venv + Geschwister-Repos + Projekt (siehe README)

# Option 2: Nur Django, im Vordergrund
python examples/run_knowledge_django.py

# Option 3: Manuell
python manage.py migrate
python manage.py runserver
```

`kistack` ruft `deploy/devstack.py` mit `.venv/bin/python` auf (auch als Symlink, z. B.
nach `~/bin/kistack`). Gestartete Dienste laufen losgelöst vom Terminal weiter. `stop`
beendet auch von Hand gestartete Server, aber nur, wenn sie aus diesem Projekt stammen;
ein fremder Prozess auf dem Port bleibt unangetastet. Postgres wird bei Bedarf per
`docker compose up -d postgres` (deploy/postgres, `.env` nötig) gestartet, Ollama nur
geprüft. Hosts/Ports pro Rechner in `deploy/stack.env` (Vorlage
`deploy/stack.env.example`, nicht in git): `KI_DJANGO_HOST/PORT`, `KI_API_HOST/PORT`,
`KI_PG_HOST/PORT`, `KI_OLLAMA_URL`; Umgebungsvariablen haben Vorrang. Alle Einträge gehen
an die Dienste weiter, also auch `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS` usw.
Django bekommt `KNOWLEDGE_API_URL` passend zum API-Port. Auch der Prod-Host läuft so mit
`runserver` (mit `--insecure`, damit statische Dateien ohne DEBUG funktionieren) – bewusst
einfach, nicht für das offene Internet gedacht.

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
