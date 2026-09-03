from __future__ import annotations

import os
from pathlib import Path

from ki_core.config import Config


BASE_DIR = Path(__file__).resolve().parents[2]
_CONFIG = Config.from_env()
DATA_DIR = Path(
    os.getenv(
        "KICLI_DATA_ROOT",
        os.getenv(
            "KNOWLEDGE_MARKDOWN_DIR",
            _CONFIG.knowledge_data_root or str(Path.home() / "dev_data" / "ki-knowledge"),
        ),
    )
).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DB_PATH = os.getenv("KNOWLEDGE_DB_PATH", str(DATA_DIR / "knowledge.db"))
DJANGO_DB_PATH = os.getenv("DJANGO_DB_PATH", str(DATA_DIR / "django.sqlite3"))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-ki-knowledge-site")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ki_knowledge.django_site",
    # Wagtail: parallel CMS/workflow layer on top of the canonical
    # data-source core (see ki_knowledge.wagtail_cms). Introduced as an
    # additive layer, not a replacement for existing infosite views.
    "ki_knowledge.wagtail_cms",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "ki_knowledge.django_site.urls"
WSGI_APPLICATION = "ki_knowledge.django_site.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DJANGO_DB_PATH,
    }
}

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [str(BASE_DIR / "static")] if (BASE_DIR / "static").exists() else []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "ki_knowledge" / "django_site" / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ki_knowledge.django_site.context_processors.active_domain",
                "ki_knowledge.django_site.context_processors.nav_areas",
            ],
        },
    }
]

LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Wagtail settings (parallel CMS/workflow layer)
WAGTAIL_SITE_NAME = "ki-knowledge CMS"
WAGTAILADMIN_BASE_URL = os.getenv("WAGTAILADMIN_BASE_URL", "http://localhost:8000")
WAGTAIL_ENABLE_UPDATE_CHECK = False

# Ki-core configuration for services
KI_CONFIG = Config(knowledge_data_root=str(DATA_DIR))
