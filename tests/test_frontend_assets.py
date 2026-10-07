"""Frontend template contracts; no database access or database fixtures."""

import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

from django.db.backends.utils import CursorWrapper
from django.template.loader import render_to_string as django_render_to_string
from django.urls import reverse
import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "ki_knowledge/django_site/templates"
STATIC = ROOT / "ki_knowledge/django_site/static"
WIDGETKIT_STATIC = ROOT.parent / "widgetkit-django/widgetkit_django/static"
PROJECT = SimpleNamespace(
    id=7, title='Quotes " & </script> ü', domain='a"&b',
    working_title="notes", enabled=True, source_directory="", output_dir="",
    display_source_dir="", display_output_dir="", generation_status="pending",
    sync_status="pending", html_site_generated=False, description="",
    generation_error="",
)


def render_to_string(template, context):
    return django_render_to_string(template, {"csrf_token": "test-token", **context})


@pytest.fixture(autouse=True)
def forbid_database_queries(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Frontend asset tests must not query a database")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)


class PageData(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = {}
        self.scripts = {}
        self.script_id = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.elements[attrs["id"]] = attrs
        if tag == "script" and attrs.get("type") == "application/json":
            self.script_id = attrs["id"]
            self.scripts[self.script_id] = ""

    def handle_data(self, data):
        if self.script_id:
            self.scripts[self.script_id] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.script_id = None

    def payload(self, element_id):
        return json.loads(self.scripts[element_id])


def test_all_repository_templates_have_no_executable_or_stylesheet_blocks():
    templates = list((ROOT / "ki_knowledge").rglob("*.html"))
    assert templates
    for path in templates:
        html = path.read_text()
        assert not re.search(r"<style\b", html, re.I), path
        for attrs, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
            if body.strip():
                assert re.search(r'type=["\']application/json["\']', attrs), path


@pytest.mark.parametrize("template,asset", [
    ("document_preview.html", "django_site/js/document-preview.js"),
    ("infosite/ai_refine.html", "infosite/js/ai-refine.js"),
    ("infosite/project_detail.html", "infosite/js/project-detail.js"),
    ("infosite/preview.html", "infosite/js/preview.js"),
    ("infosite/import_control.html", "infosite/js/import-control.js"),
    ("infosite/knowledge_blocks.html", "infosite/js/knowledge-blocks.js"),
    ("kicli_django/records.html", "django_site/js/bulk-selection.js"),
    ("kicli_django/artifacts.html", "django_site/js/bulk-selection.js"),
    ("kicli_django/jobs.html", "django_site/js/bulk-selection.js"),
    ("kicli_django/jira_support_chat.html", "django_site/js/jira-support-chat.js"),
    ("kicli_django/settings_layout.html", "django_site/js/settings-layout.js"),
    ("kicli_django/pdf_import_jobs.html", "django_site/js/pdf-import-jobs.js"),
    ("kicli_django/graph_3d.html", "django_site/js/graph-3d.js"),
    ("kicli_django/widget_shell_builder.html", "django_site/js/widget-shell-builder.js"),
    ("kicli_django/widget_catalog.html", "widgetkit_django/js/widget-catalog.js"),
])
def test_pages_render_with_existing_static_assets(template, asset):
    html = render_to_string(template, {
        "project": PROJECT, "stats": {}, "summary": {},
        "report": {"counts": {}}, "active_domain": PROJECT.domain,
        "site_structure_json": "[]", "source_tree": [],
        "initial_site_structure": [], "display_mode": "table",
        "graph_3d": {"nodes": [], "edges": []},
        "active_preset_json": None, "widget_preview_payload": [],
    })
    assert asset in html
    asset_root = WIDGETKIT_STATIC if asset.startswith("widgetkit_django/") else STATIC
    asset_path = asset_root / asset
    assert asset_path.is_file()
    assert not re.search(r"\{\{|\{%|\{#", asset_path.read_text())
    for reference in re.findall(r'{% static [\'"]([^\'"]+)[\'"] %}', (TEMPLATES / template).read_text()):
        reference_root = WIDGETKIT_STATIC if reference.startswith("widgetkit_django/") else STATIC
        assert (reference_root / reference).is_file()


def test_catalog_payload_is_a_list_not_a_json_string():
    payload = [{"widget_id": "demo", "description": PROJECT.title,
                "rows": [], "stats": [], "links": []}]
    html = render_to_string("kicli_django/widget_catalog.html", {
        "widget_preview_payload": payload,
        "widget_catalog": [{"widget_id": "demo", "label": "Demo"}],
        "area_tabs": [],
    })
    page = PageData(html)
    assert page.payload("widget-preview-payload") == payload
    assert "\\u003C/script\\u003E" in page.scripts["widget-preview-payload"]
    css = (WIDGETKIT_STATIC / "widgetkit_django/css/widget-catalog.css").read_text()
    for selector in (".wk-catalog-shell", ".wk-catalog-preview", ".wk-catalog-size"):
        assert selector in css


def test_document_and_hierarchy_json_round_trip_without_double_encoding():
    documents = [{"id": "a", "name": PROJECT.title, "path": "a.md",
                  "type": "markdown", "size_display": "1 KB", "url": "/api/a"}]
    html = render_to_string("document_preview.html", {"project": PROJECT, "documents": documents})
    assert PageData(html).payload("document-preview-data") == documents
    tree = [{"title": PROJECT.title, "children": [], "path": 'a"&b.md'}]
    html = render_to_string("infosite/project_detail.html", {
        "project": PROJECT, "source_tree": tree, "initial_site_structure": tree,
        "site_structure_json": json.dumps(tree),
    })
    page = PageData(html)
    assert page.payload("source-tree-json") == tree
    assert page.payload("initial-site-structure-json") == tree
    assert json.loads(page.elements["site-structure-hidden"]["value"]) == tree


def test_knowledge_export_and_publish_configuration_are_escaped_data():
    stats = {"total_blocks": 3, "total_files": 1, "sections": 1}
    html = render_to_string("infosite/knowledge_blocks.html", {
        "project": PROJECT, "stats": stats, "csrf_token": "test-token",
    })
    page = PageData(html)
    config = page.elements["knowledge-block-actions"]
    assert config["data-project-title"] == PROJECT.title
    assert config["data-domain"] == PROJECT.domain
    assert config["data-project-id"] == "7"
    assert config["data-publish-url"] == reverse("infosite:publish_blocks", args=[PROJECT.id])
    assert page.payload("knowledge-block-stats") == stats
    assert 'value="test-token"' in html
    assert "onclick=" not in html


def test_shell_and_pdf_polling_config_round_trip():
    preset = {"label": PROJECT.title, "widget_id": "demo"}
    html = render_to_string("kicli_django/widget_shell_builder.html", {
        "active_widget_id": PROJECT.title, "active_preset_json": preset,
    })
    page = PageData(html)
    assert page.payload("widget-shell-active-preset") == preset
    assert f'data-active-preset-id="Quotes &quot; &amp; &lt;/script&gt; ü"' in html
    assert "widgetShellBuilderConfig" not in html
    assert "PRESET_ID" in html
    html = render_to_string("kicli_django/pdf_import_jobs.html", {
        "active_domain": PROJECT.domain, "status_filter": 'a"&b',
        "summary": {"pending": 1, "processing": 2, "done": 3, "failed": 4},
        "report": {"counts": {}}, "worker_run": {"token": "x", "status": "running"},
    })
    config = PageData(html).elements["pdf-job-refresh-config"]
    assert config["data-domain"] == PROJECT.domain
    assert config["data-status"] == 'a"&b'
    assert config["data-current"] == "1:2:3:4:x:running"


def run_node(code):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    subprocess.run([node, "-e", code], check=True, cwd=ROOT, capture_output=True, text=True)


def test_shared_selection_respects_form_ownership_and_external_controls():
    source = (STATIC / "django_site/js/bulk-selection.js").read_text()
    run_node("""
const assert = require('node:assert/strict');
let listener;
global.document = { addEventListener: (name, callback) => { listener = callback; } };
global.HTMLInputElement = class {
  constructor(name) { this.name = name; this.type = 'checkbox'; this.checked = false; }
  matches() { return true; }
};
""" + source + """
const own = new HTMLInputElement('job_ids');
const other = new HTMLInputElement('record_ids');
const externalMaster = new HTMLInputElement('');
externalMaster.dataset = { selectAll: 'job_ids' };
externalMaster.form = { elements: [own, other, externalMaster] };
externalMaster.checked = true;
listener({ target: externalMaster });
assert.equal(own.checked, true);
assert.equal(other.checked, false);
externalMaster.checked = false;
listener({ target: externalMaster });
assert.equal(own.checked, false);
""")


def test_catalog_loader_renders_real_readonly_body_and_escaped_metadata():
    source = (WIDGETKIT_STATIC / "widgetkit_django/js/widget-catalog.js").read_text()
    run_node("""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.innerHTML = ''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attrs[name] = value; }
}
const preview = new Element('div');
const payload = [
  { widget_id: 'demo', label: '<img src=x onerror=bad()>', description: '<script>bad()</script>',
    active_domain: 'research<&', status: 'sample', note: '',
    body_html: '<table><tbody><tr><td>Real row</td></tr></tbody></table>' },
  { widget_id: 'second', label: 'Second', description: 'Planned feature',
    active_domain: 'research<&', status: 'planned', note: 'Not implemented',
    body_html: '<p>Planned quiz</p>' },
];
let active = false;
let selectSecond;
const button = { dataset: { widgetId: 'demo' },
  classList: { toggle: (name, value) => { active = value; } },
  setAttribute(name, value) { this[name] = value; },
  addEventListener() {} };
const secondButton = { dataset: { widgetId: 'second' },
  classList: { toggle() {} }, setAttribute() {},
  addEventListener(name, callback) { selectSecond = callback; } };
global.document = {
  getElementById: (id) => id === 'widget-preview' ? preview : { textContent: JSON.stringify(payload) },
  querySelectorAll: () => [button, secondButton],
  createElement: (tag) => new Element(tag),
};
""" + source + """
assert.equal(active, true);
assert.equal(button['aria-pressed'], 'true');
let card = preview.children[0];
const head = card.children[0];
assert.equal(head.children[0].textContent, payload[0].label);
assert.equal(head.children[0].innerHTML, '');
assert.equal(card.children.length, 2);
let body = card.children[1];
assert.equal(body.attrs.inert, '');
assert.equal(body.innerHTML, payload[0].body_html);
assert.equal(preview.children[1].textContent, payload[0].description);
let code = preview.children[2].children[1];
assert.equal(code.textContent, payload[0].body_html);
assert.equal(code.innerHTML, '');
selectSecond();
assert.equal(active, false);
card = preview.children[0];
assert.equal(card.children[2].innerHTML, payload[1].body_html);
assert.equal(card.children[1].textContent, 'Not implemented');
""")


def test_knowledge_actions_use_json_stats_and_explicit_click_target():
    source = (STATIC / "infosite/js/knowledge-blocks.js").read_text()
    run_node("""
const assert = require('node:assert/strict');
const callbacks = {};
const button = { disabled: false, textContent: 'Publish',
  addEventListener: (name, callback) => { callbacks.publish = callback; } };
const exportButton = {
  addEventListener: (name, callback) => { callbacks.export = callback; } };
const config = { publishUrl: '/publish/', projectTitle: 'Quotes " & ü',
  domain: 'demo', workingTitle: 'notes', projectId: '7' };
let exportData;
let downloadName;
global.document = {
  addEventListener: (name, callback) => callback(),
  getElementById: (id) => id === 'knowledge-block-actions'
    ? { dataset: config, querySelector: (selector) =>
      selector === '[data-publish-blocks]' ? button : exportButton }
    : { textContent: '{"total_blocks":3}' },
  querySelector: () => ({ value: 'token' }),
  querySelectorAll: () => [],
  createElement: () => ({ set download(value) { downloadName = value; }, click() {} })
};
global.Blob = class { constructor(parts) { exportData = JSON.parse(parts[0]); } };
global.URL = { createObjectURL: () => 'blob:test', revokeObjectURL() {} };
global.confirm = () => true;
global.alert = () => {};
global.setTimeout = () => {};
global.fetch = async (url, options) => {
  assert.equal(url, '/publish/');
  assert.equal(options.method, 'POST');
  assert.equal(options.headers['X-CSRFToken'], 'token');
  assert.equal(button.disabled, true);
  return { ok: true, json: async () => ({
    blocks_stored: 3, files_processed: 1, source_id: 'source'
  }) };
};
""" + source + """
callbacks.export();
assert.equal(exportData.project, config.projectTitle);
assert.deepEqual(exportData.stats, { total_blocks: 3 });
assert.equal(downloadName, 'knowledge-blocks-7.json');
(async () => {
  await callbacks.publish({ currentTarget: button, target: {} });
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Publish');
})().catch(error => { console.error(error); process.exitCode = 1; });
""")


def test_ai_refinement_empty_page_has_no_runtime_error():
    source = (STATIC / "infosite/js/ai-refine.js").read_text()
    run_node("global.document = { getElementById: () => null };\n" + source)
