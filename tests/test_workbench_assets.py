"""Verify the shipped React entry, lazy language chunk and local worker."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "ki_knowledge/django_site/static/django_site/workbench"


def test_workbench_bundle_is_self_contained():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    entry = manifest["src/main.tsx"]
    assert entry["isEntry"]
    assert (ASSETS / entry["file"]).is_file()
    for path in entry["css"]:
        assert (ASSETS / path).is_file()
    for path in ASSETS.glob("assets/*"):
        assert path.stat().st_size > 0
    assert list(ASSETS.glob("assets/editor.worker-*.js"))
    assert list(ASSETS.glob("assets/markdown-*.js"))
    notices = (ASSETS / "THIRD-PARTY-NOTICES.txt").read_text()
    assert "monaco-editor / LICENSE" in notices and "react / LICENSE" in notices


def test_workbench_template_keeps_csrf_and_disables_cdn_htmx():
    template = (ROOT / "ki_knowledge/django_site/templates/kicli_django/workbench.html").read_text()
    assert '{% block htmx_script %}{% endblock %}' in template
    assert 'json_script:"workbench-bootstrap"' in template
    assert "{% csrf_token %}" in template
    assert 'type="module"' in template
