from __future__ import annotations

import os
from pathlib import Path

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import config as runtime_config, knowledge_data_root, knowledge_db_path, knowledge_store_target
from ki_knowledge.data_layout import DataLayout


BASE_DIR = Path(__file__).resolve().parents[2]
_CONFIG = runtime_config()
DATA_DIR = knowledge_data_root(_CONFIG)
DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DB_PATH = str(knowledge_db_path(_CONFIG))
KNOWLEDGE_STORE_TARGET = knowledge_store_target(_CONFIG)
DJANGO_DB_PATH = os.getenv("DJANGO_DB_PATH", str(DataLayout(DATA_DIR).django_db_path()))
for _db_path in (KNOWLEDGE_DB_PATH, DJANGO_DB_PATH):
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

POSTGRES_DSN = (
    os.getenv("KI_KNOWLEDGE_POSTGRES_DSN", "").strip()
    or getattr(_CONFIG, "distributed_postgres_dsn", "").strip()
)

# apps.ki_knowledge.django.* from ki.yaml; DJANGO_* env vars override per process.
_DJANGO_CFG = _CONFIG.raw.get_path("apps.ki_knowledge.django", {}) or {}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or _DJANGO_CFG.get("secret_key") or "django-insecure-ki-knowledge-site"
_debug_env = os.getenv("DJANGO_DEBUG")
DEBUG = (
    _debug_env.lower() in {"1", "true", "yes"} if _debug_env is not None else bool(_DJANGO_CFG.get("debug", False))
)
ALLOWED_HOSTS = (
    os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if os.getenv("DJANGO_ALLOWED_HOSTS") else None
) or list(_DJANGO_CFG.get("allowed_hosts") or ["*"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ki_knowledge.django_site",
    "widgetkit_django",
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
if POSTGRES_DSN:
    INSTALLED_APPS.append("django.contrib.postgres")

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

if POSTGRES_DSN:
    import dj_database_url

    DATABASES["default"] = dj_database_url.parse(POSTGRES_DSN, conn_max_age=600)
    # Read-only source for `migrate_django_db_to_postgres`; never written to.
    if Path(DJANGO_DB_PATH).is_file():
        DATABASES["sqlite_legacy"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": DJANGO_DB_PATH}

# Default dev cache: safe local caching for repeated dashboard metadata and
# template fragments without requiring an external cache service.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
USE_REDIS_CACHE = os.getenv("USE_REDIS_CACHE", "").strip().lower() in {"1", "true", "yes"}

if USE_REDIS_CACHE and REDIS_URL:
    try:
        import django_redis  # noqa: F401
    except ImportError:
        USE_REDIS_CACHE = False

if USE_REDIS_CACHE and REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "ki-knowledge",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ki-knowledge-dev-cache",
            "TIMEOUT": 300,
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

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

LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Wagtail settings (parallel CMS/workflow layer)
WAGTAIL_SITE_NAME = "ki-knowledge CMS"
WAGTAILADMIN_BASE_URL = (
    os.getenv("WAGTAILADMIN_BASE_URL") or _DJANGO_CFG.get("wagtail_admin_base_url") or "http://localhost:8000"
)
WAGTAIL_ENABLE_UPDATE_CHECK = False

# Ki-core configuration for services
KI_CONFIG = Config(knowledge_data_root=str(DATA_DIR))
