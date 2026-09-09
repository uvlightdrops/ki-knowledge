from __future__ import annotations

from typing import Any

from django.middleware.csrf import get_token
from django.urls import reverse

from .dashboard_registry import widget_by_id
from .infosite_models import Domain, GeneratedDocument


def _card(widget_id: str, *, label: str, description: str, body: str, width: int = 6) -> dict[str, Any]:
    return {"widget_id": widget_id, "label": label, "description": description, "body": body, "width": max(3, min(int(width), 12))}


def _widget_width(spec: Any, *, widget_widths: dict[str, int] | None = None) -> int:
    if spec is None:
        return 6
    resolved = (widget_widths or {}).get(getattr(spec, "widget_id", ""), getattr(spec, "default_w", 6))
    try:
        width = int(resolved)
    except (TypeError, ValueError):
        width = int(getattr(spec, "default_w", 6))
    return max(3, min(width, 12))


def build_widget_preview_payload(*, widget_ids: list[str]) -> list[dict[str, str]]:
    """Return lightweight HTML payloads for the dashboard builder preview pane.

    The preview should show the effective card layout and the exact HTML source
    that would be embedded for a widget, without dumping raw registry metadata as
    JSON in the UI.
    """
    payload: list[dict[str, str]] = []
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue

        if widget_id == "datasources.domain.overview.v1":
            preview_html = (
                "<div class='card'>"
                "<h4>Domains</h4>"
                "<table><thead><tr><th>Domain</th><th>Sources</th><th>Records</th></tr></thead><tbody>"
                "<tr><td>default</td><td>12</td><td>48</td></tr>"
                "<tr><td>demo</td><td>7</td><td>21</td></tr>"
                "</tbody></table>"
                "</div>"
            )
        elif widget_id == "datasources.overview.summary.v1":
            preview_html = (
                "<div class='card'>"
                "<p><strong>Sources:</strong> 19</p>"
                "<p><strong>Markdown files:</strong> 81</p>"
                "<p><strong>OWL sources:</strong> 3</p>"
                "</div>"
            )
        elif widget_id == "datasources.import.quick.v1":
            preview_html = (
                "<div class='card'>"
                "<p><a href='/data-sources/import/'>Import</a></p>"
                "<p><a href='/data-sources/workspace/'>Workspace</a></p>"
                "<p><a href='/data-sources/pdf/'>PDF jobs</a></p>"
                "<button type='button'>Import PDF</button>"
                "</div>"
            )
        elif widget_id == "datasources.sources.discovery.v1":
            preview_html = (
                "<div class='card'>"
                "<p><strong>Files:</strong> 81</p>"
                "<p><strong>Sources:</strong> 19</p>"
                "<p><a href='/data-sources/sources/'>Open sources</a></p>"
                "</div>"
            )
        elif widget_id == "datasources.jobs.recent.v1":
            preview_html = (
                "<div class='card'>"
                "<p><a href='/knowledge/jobs/'>View semantic jobs</a></p>"
                "<p><a href='/data-sources/pdf/'>View PDF jobs</a></p>"
                "</div>"
            )
        elif widget_id == "datasources.source.list.v1":
            preview_html = (
                "<div class='card'>"
                "<h4>Source list</h4>"
                "<div class='grid'><div class='card'><h5>Article</h5><p>source metadata</p></div></div>"
                "</div>"
            )
        elif widget_id == "datasources.ai.summary.v1":
            preview_html = (
                "<div class='card'>"
                "<p>Ollama chat overview.</p>"
                "<p><a href='/knowledge/chat/ollama/'>Open chat</a></p>"
                "</div>"
            )
        elif widget_id == "knowledge.overview.summary.v1":
            preview_html = (
                "<div class='card'>"
                "<p><strong>Sources:</strong> 26</p>"
                "<p><strong>Records:</strong> 132</p>"
                "<p><strong>Artifacts:</strong> 19</p>"
                "</div>"
            )
        elif widget_id == "knowledge.semantic.monitor.v1":
            preview_html = (
                "<div class='card'>"
                "<p><a href='/knowledge/semantic/'>Semantic Layer</a></p>"
                "<p><a href='/knowledge/jobs/'>Jobs</a></p>"
                "</div>"
            )
        elif widget_id == "knowledge.semantic.quick.v1":
            preview_html = (
                "<div class='card'>"
                "<p><a href='/knowledge/semantic/domain-analysis/'>Domain analysis</a></p>"
                "<p><a href='/knowledge/semantic/hybrid-search/'>Hybrid search</a></p>"
                "<p><a href='/knowledge/semantic/graph-explorer/'>Graph explorer</a></p>"
                "</div>"
            )
        elif widget_id == "knowledge.records.summary.v1":
            preview_html = "<div class='card'><p><strong>Records:</strong> 132</p><p><a href='/knowledge/records/'>Open records</a></p></div>"
        elif widget_id == "knowledge.artifacts.summary.v1":
            preview_html = "<div class='card'><p><strong>Artifacts:</strong> 19</p><p><a href='/knowledge/artifacts/'>Open artifacts</a></p></div>"
        elif widget_id == "knowledge.tools.summary.v1":
            preview_html = (
                "<div class='card'>"
                "<div class='card'><h5>Knowledge API</h5><p>Search and inspect browser context.</p></div>"
                "<div class='card'><h5>Records</h5><p>Browse records.</p></div>"
                "</div>"
            )
        elif widget_id == "infooutput.overview.summary.v1":
            preview_html = "<div class='card'><p><a href='/output/infosite/dashboard/'>Open infosite dashboard</a></p></div>"
        elif widget_id == "infooutput.infosite.recent.v1":
            preview_html = "<div class='card'><p><a href='/output/infosite/dashboard/'>Open recent infosites</a></p></div>"
        elif widget_id == "infooutput.documents.recent.v1":
            preview_html = (
                "<div class='card'><table><thead><tr><th>File</th><th>Project</th></tr></thead><tbody>"
                "<tr><td>daily-overview.md</td><td>demo</td></tr>"
                "</tbody></table></div>"
            )
        elif widget_id == "infooutput.formats.summary.v1":
            preview_html = "<div class='card'><p>Infosite <span class='chip'>aktiv</span></p><p>Quiz <span class='chip'>geplant</span></p></div>"
        elif widget_id == "infooutput.domain.overview.v1":
            preview_html = (
                "<div class='card'><table><thead><tr><th>Domain</th><th>Total</th></tr></thead><tbody>"
                "<tr><td>default</td><td>42</td></tr>"
                "</tbody></table></div>"
            )
        elif widget_id == "admin.domain.management.v1":
            preview_html = "<div class='card'><p><strong>Active domain:</strong> default</p><p><a href='/settings/layout/builder/?area=admin'>Open admin layout</a></p></div>"
        elif widget_id == "admin.domain.db.overview.v1":
            preview_html = (
                "<div class='card'><table><thead><tr><th>Domain</th><th>Sources</th><th>Knowledge</th><th>Projects</th><th>Outputs</th></tr></thead>"
                "<tbody><tr><td>default</td><td>12</td><td>48</td><td>3</td><td>11</td></tr>"
                "<tr><td>demo</td><td>7</td><td>21</td><td>2</td><td>9</td></tr></tbody></table></div>"
            )
        elif widget_id == "admin.system.status.v1":
            preview_html = "<div class='card'><p><strong>Builder:</strong> active</p><p><strong>Admin area:</strong> enabled</p></div>"
        elif widget_id == "settings.layout.registry.v1":
            preview_html = "<div class='card'><p>Layout registry</p><p>Configuration for layout preferences.</p></div>"
        elif widget_id == "settings.config.summary.v1":
            preview_html = "<div class='card'><p>Config summary</p><p>Current workspace configuration overview.</p></div>"
        else:
            preview_html = f"<div class='card'><p class='muted'>{spec.description}</p></div>"

        payload.append(
            {
                "widget_id": widget_id,
                "preview_html": preview_html,
                "source_html": preview_html,
            }
        )
    return payload


def build_data_sources_widget_cards(
    *,
    request: Any,
    active_domain: str,
    all_domains: list[dict[str, Any]],
    active_domain_state: dict[str, Any],
    markdown_count: int,
    data_dir: str,
    jira_issues: int,
    jira_csv_path: str,
    jira_cache_db: str,
    pdf_count: int,
    pdf_dir: str,
    pdf_jobs: dict[str, Any],
    ontology_count: int,
    ontology_dir: str,
    owl_sources: int,
    sources: list[Any],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    csrf_token = get_token(request) if request is not None else ""
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        width = _widget_width(spec, widget_widths=widget_widths)
        if widget_id == "datasources.domain.overview.v1":
            rows = []
            for domain in all_domains:
                rows.append(
                    "<tr>"
                    f"<td><strong>{domain['display_name']}</strong></td>"
                    f"<td>{domain['knowledge_sources']}</td>"
                    f"<td>{domain['knowledge_records']}</td>"
                    f"<td>{domain['infosite_project_count']}</td>"
                    f"<td>{domain['infosite_source_count']}</td>"
                    "</tr>"
                )
            body = (
                "<table><thead><tr><th>Domain</th><th>Sources</th><th>Records</th><th>InfoSites</th><th>Files</th></tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
                + "<div style='display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;'>"
                + "".join(
                    f"<a class='chip' href='?domain={d['slug']}' {'style=\'border-color:#60a5fa;color:#fff\'' if d['is_active'] else ''}>{d['display_name']}</a>"
                    for d in all_domains
                )
                + "</div>"
            )
        elif widget_id == "datasources.overview.summary.v1":
            body = (
                f"<p><strong>Sources:</strong> {len(sources)}</p>"
                f"<p><strong>Markdown files:</strong> {markdown_count}</p>"
                f"<p><strong>OWL sources:</strong> {owl_sources}</p>"
            )
        elif widget_id == "datasources.import.quick.v1":
            body = (
                "<p><a href=\"/data-sources/import/\">Import</a></p>"
                "<p><a href=\"/data-sources/workspace/\">Workspace</a></p>"
                "<p><a href=\"/data-sources/pdf/\">PDF jobs</a></p>"
                "<form id='pdf-import-form' method='post' action='/data-sources/import/' class='section'>"
                "<input type='hidden' name='import_type' value='directory'>"
                "<input type='hidden' name='next' value='data-sources'>"
                f"<input type='hidden' name='csrfmiddlewaretoken' value='{csrf_token}'>"
                "<label for='pdf_path'>PDF path or folder</label><br>"
                "<input id='pdf_path' name='path' type='text' value='' placeholder='/path/to/file.pdf oder /path/to/folder' style='width:100%;margin-top:6px'>"
                "<div style='margin-top:8px'><button type='submit'>Import PDF</button></div>"
                "</form>"
            )
        elif widget_id == "datasources.sources.discovery.v1":
            body = (
                f"<p><strong>Files:</strong> {markdown_count}</p>"
                f"<p><strong>Sources:</strong> {len(sources)}</p>"
                "<p><a href=\"/data-sources/sources/\">Open sources</a></p>"
            )
        elif widget_id == "datasources.jobs.recent.v1":
            body = (
                "<p><a href=\"/knowledge/jobs/\">View semantic jobs</a></p>"
                "<p><a href=\"/data-sources/pdf/\">View PDF jobs</a></p>"
            )
        elif widget_id == "datasources.source.list.v1":
            source_cards = []
            for source in sources[:12]:
                title = getattr(source, "title", None) or str(source.get("title", "Untitled source"))
                source_id = getattr(source, "source_id", None) or str(source.get("source_id", ""))
                loc = getattr(source, "location", None) or str(source.get("location", ""))
                source_cards.append(
                    "<div class='card'>"
                    f"<h4><a href='{reverse('source-detail', args=[source_id])}'>{title}</a></h4>"
                    f"<p class='muted'><span class='chip'>{getattr(source, 'source_type', None) or str(source.get('source_type', 'source'))}</span></p>"
                    f"<p class='mono'>{loc}</p>"
                    "</div>"
                )
            body = "<div class='grid'>" + "".join(source_cards) + "</div>" if source_cards else "<p class='muted'>No sources.</p>"
        elif widget_id == "datasources.markdown.files.v1":
            body = (
                f"<p><strong>Markdown files:</strong> {markdown_count}</p>"
                "<p><a href=\"/data-sources/workspace/\">Open workspace</a></p>"
                "<p><a href=\"/data-sources/sources/\">Browse sources</a></p>"
            )
        elif widget_id == "datasources.ontology.overview.v1":
            body = (
                f"<p><strong>Ontology files:</strong> {ontology_count}</p>"
                f"<p><strong>OWL sources:</strong> {owl_sources}</p>"
                f"<p><a href=\"{ontology_dir}\">Open ontology folder</a></p>"
            )
        elif widget_id == "datasources.ai.summary.v1":
            body = (
                f"<p><strong>Domain:</strong> {active_domain}</p>"
                "<p><strong>Workspace:</strong> markdown + OCR/PDF import pipeline</p>"
                "<p><a href=\"/knowledge/chat/ollama/\">Ollama Chat öffnen</a></p>"
                "<p><a href=\"/knowledge/chat/support/\">Support Chat</a></p>"
            )
        else:
            body = f"<p class='muted'>{spec.description}</p>"
        width = _widget_width(spec, widget_widths=widget_widths)
        cards.append(_card(widget_id, label=spec.label, description=spec.description, body=body, width=width))
    return cards


def build_knowledge_widget_cards(
    *,
    active_domain: str,
    scoped_knowledge: dict[str, Any],
    quick_links: list[tuple[str, str, str]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        if widget_id == "knowledge.overview.summary.v1":
            body = (
                "<p><strong>Sources:</strong> "
                f"{int(scoped_knowledge['sources'])}</p>"
                "<p><strong>Records:</strong> "
                f"{int(scoped_knowledge['records'])}</p>"
                "<p><strong>Artifacts:</strong> "
                f"{int(scoped_knowledge['artifacts'])}</p>"
            )
        elif widget_id == "knowledge.semantic.monitor.v1":
            body = (
                "<p><a href=\"/knowledge/semantic/\">Semantic Layer</a></p>"
                "<p><a href=\"/knowledge/jobs/\">Jobs</a></p>"
            )
        elif widget_id == "knowledge.semantic.quick.v1":
            body = (
                "<p><a href=\"/knowledge/semantic/domain-analysis/\">Domain analysis</a></p>"
                "<p><a href=\"/knowledge/semantic/hybrid-search/\">Hybrid search</a></p>"
                "<p><a href=\"/knowledge/semantic/graph-explorer/\">Graph explorer</a></p>"
            )
        elif widget_id == "knowledge.records.summary.v1":
            body = (
                f"<p><strong>Records:</strong> {int(scoped_knowledge['records'])}</p>"
                "<p><a href=\"/knowledge/records/\">Open records</a></p>"
            )
        elif widget_id == "knowledge.artifacts.summary.v1":
            body = (
                f"<p><strong>Artifacts:</strong> {int(scoped_knowledge['artifacts'])}</p>"
                "<p><a href=\"/knowledge/artifacts/\">Open artifacts</a></p>"
            )
        elif widget_id == "knowledge.api.browser.v1":
            body = (
                f"<p><strong>Domain:</strong> {active_domain}</p>"
                f"<p><strong>Sources:</strong> {int(scoped_knowledge['sources'])}</p>"
                f"<p><strong>Records:</strong> {int(scoped_knowledge['records'])}</p>"
                "<p><a href=\"/knowledge/api/\">Open Knowledge API</a></p>"
                "<p><a href=\"/knowledge/records/\">Browse records</a></p>"
            )
        elif widget_id == "knowledge.jobs.recent.v1":
            body = (
                f"<p><strong>Domain:</strong> {active_domain}</p>"
                "<p><a href=\"/knowledge/jobs/\">Open jobs</a></p>"
                "<p><a href=\"/knowledge/semantic/\">Semantic layer</a></p>"
                f"<p><strong>Artifacts:</strong> {int(scoped_knowledge['artifacts'])}</p>"
            )
        elif widget_id == "knowledge.graph.overview.v1":
            body = (
                f"<p><strong>Active domain:</strong> {active_domain}</p>"
                f"<p><strong>Records:</strong> {int(scoped_knowledge['records'])}</p>"
                f"<p><strong>Sources:</strong> {int(scoped_knowledge['sources'])}</p>"
                "<p><a href=\"/knowledge/semantic/graph-explorer/\">Open graph explorer</a></p>"
            )
        elif widget_id == "knowledge.tools.summary.v1":
            items = []
            for label, url, description in quick_links:
                items.append(
                    "<div class='card'>"
                    f"<h4><a href='{url}' title='{description}'>{label}</a></h4>"
                    f"<p class='muted'>{description}</p>"
                    "</div>"
                )
            body = "<div class='grid'>" + "".join(items) + "</div>"
        else:
            body = f"<p class='muted'>{spec.description}</p>"
        width = _widget_width(spec, widget_widths=widget_widths)
        cards.append(_card(widget_id, label=spec.label, description=spec.description, body=body, width=width))
    return cards


def build_output_widget_cards(
    *,
    active_domain: str,
    domain_stats: list[dict[str, Any]],
    recent_documents: list[Any],
    formats: list[dict[str, Any]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        if widget_id == "infooutput.overview.summary.v1":
            body = "<p><a href=\"/output/infosite/dashboard/\">Open infosite dashboard</a></p>"
        elif widget_id == "infooutput.infosite.recent.v1":
            body = "<p><a href=\"/output/infosite/dashboard/\">Open recent infosites</a></p>"
        elif widget_id == "infooutput.documents.recent.v1":
            body = (
                "<table><thead><tr><th>File</th><th>Project</th><th>Status</th></tr></thead><tbody>"
                + "".join(
                    f"<tr><td class='mono'><a href='{reverse('infosite:project_detail', args=[doc.project_id])}'>{doc.display_path}</a></td><td>{doc.project.title}</td><td><span class='chip'>{doc.get_review_status_display()}</span></td></tr>"
                    for doc in recent_documents[:5]
                )
                + "</tbody></table>"
            )
        elif widget_id == "infooutput.formats.summary.v1":
            entries = []
            for fmt in formats:
                if fmt.get("url"):
                    entries.append(f"<p><a href='{fmt['url']}'>{fmt['label']}</a> <span class='chip'>{fmt['status']}</span></p>")
                else:
                    entries.append(f"<p>{fmt['label']} <span class='chip'>{fmt['status']}</span></p>")
            body = "".join(entries)
        elif widget_id == "infooutput.domain.overview.v1":
            rows = "".join(
                f"<tr><td><strong>{d['display_name']}</strong></td><td>{d['total']}</td><td>{d['none']}</td><td>{d['in_review']}</td><td>{d['approved']}</td><td>{d['rejected']}</td></tr>"
                for d in domain_stats
            )
            body = (
                "<table><thead><tr><th>Domain</th><th>Total</th><th>None</th><th>In review</th><th>Approved</th><th>Rejected</th></tr></thead><tbody>"
                + rows
                + "</tbody></table>"
            )
        else:
            body = f"<p class='muted'>{spec.description}</p>"
        width = _widget_width(spec, widget_widths=widget_widths)
        cards.append(_card(widget_id, label=spec.label, description=spec.description, body=body, width=width))
    return cards
