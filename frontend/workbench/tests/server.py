"""Disposable browser-test server: never reads or migrates the application DB."""

import json
import os
from pathlib import Path
import signal
import shutil
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "ki_knowledge.django_site.settings"

from django.conf import settings


class BrowserProvider:
    def chat(self, request):
        if "PROVIDER_FAILURE" in request.messages[-1].content:
            from ki_core.core.errors import ProviderError

            raise ProviderError("Intentional browser-test provider failure")
        if any("replacement_markdown" in message.content for message in request.messages):
            if "MALFORMED_PROPOSAL" in request.messages[-1].content:
                return SimpleNamespace(message=SimpleNamespace(content="Keine strukturierte Antwort."))
            return SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "replacement_markdown": "# Versorgung 🍒\n\nEin klarer, bewusst geprüfter Text.\n",
                "rationale": "Die Formulierung ist kürzer; die fachliche Prüfung bleibt beim Menschen.",
            })), model="browser-mock")
        return SimpleNamespace(
            message=SimpleNamespace(content="Testantwort zur ausgewählten Quelle."),
            model="browser-mock",
        )


def main():
    def stop_server(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop_server)
    temporary = ROOT / f".workbench-browser-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        run_server(temporary)
    finally:
        shutil.rmtree(temporary)


def run_server(temporary):
    settings_project = temporary / "settings-project"
    (settings_project / "schema").mkdir(parents=True)
    shutil.copy(ROOT / "schema/ki_knowledge.schema.yaml", settings_project / "schema")
    (settings_project / "ki.yaml").write_text("llm:\n  provider: mock\n", encoding="utf-8")
    (settings_project / "creds.yaml").write_text(
        "llm:\n  providers:\n    ki:\n      api_key: browser-secret-must-stay-hidden\n", encoding="utf-8",
    )
    with patch(
        "ki_knowledge.llm_provider.chat_settings",
        return_value={"provider": "mock", "model": "browser-mock", "base_url": ""},
    ), patch("ki_knowledge.llm_provider.chat_client", return_value=BrowserProvider()):
        settings.DATABASES = {
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(temporary / "browser.sqlite3")},
        }
        settings.DEBUG = True
        settings.KNOWLEDGE_STORE_TARGET = str(temporary / "knowledge.sqlite3")
        settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
        settings.WAGTAILSEARCH_BACKENDS = {
            "default": {"BACKEND": "modelsearch.backends.database", "AUTO_UPDATE": False},
        }
        settings.TEMPLATES[0]["OPTIONS"]["context_processors"] = [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "ki_knowledge.django_site.context_processors.nav_areas",
        ]
        settings.MIDDLEWARE = [
            value for value in settings.MIDDLEWARE if "middleware_netlog" not in value
        ]
        import django

        django.setup()
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        from ki_knowledge.django_site.infosite_models import Domain, InfoSiteProject
        from ki_knowledge.integrations.knowledge_store import KnowledgeStore, KnowledgeSource

        call_command("migrate", verbosity=0, interactive=False)
        get_user_model().objects.create_superuser("browser", "browser@example.invalid", "browser-test-only")
        Domain.objects.create(slug="browser-test")
        store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
        for name, text in [
            ("Beeren", "# Versorgung 🍒\n\nWildbeeren ergänzen die Versorgung.\nCafe\u0301 bleibt offen.\n"),
            ("Planung", "# Planung\n\nVorräte sichern die Trockenperiode.\n"),
        ]:
            path = temporary / f"{name}.md"
            path.write_text(text, encoding="utf-8")
            store.upsert_source(KnowledgeSource(
                source_id=f"browser:{name}", source_type="markdown",
                title=name, location=str(path), metadata={},
            ))
        (temporary / "Unimportiert.md").write_text("# Noch ohne Import\n\nDirekt erfassbar.\n", encoding="utf-8")
        (temporary / "Hinweis.pdf").write_bytes(b"%PDF")
        assert not InfoSiteProject.objects.exists()
        def source_dir(kind, domain):
            return temporary if kind == "markdown" and domain == "browser-test" else temporary / kind / domain
        with patch("ki_knowledge.django_site.sources_browser.domain_source_dir", side_effect=source_dir), \
             patch("ki_knowledge.django_site.sources_browser.domain_jira_dir", return_value=temporary / "jira"), \
             patch("ki_knowledge.django_site.sources_browser._pdf_job_states", return_value={}), \
             patch("ki_knowledge.django_site.live_settings.PROJECT_ROOT", settings_project), \
             patch("ki_knowledge.django_site.knowledge_summary.domain_source_roots", return_value=[temporary]):
            call_command("runserver", f"127.0.0.1:{sys.argv[1]}", use_reloader=False, verbosity=0)


if __name__ == "__main__":
    main()
