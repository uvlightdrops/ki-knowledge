from __future__ import annotations

from .services import default_semantic_domain, normalize_semantic_domain


def active_domain(request):
    raw = request.session.get("semantic_active_domain", "")
    if raw:
        resolved = normalize_semantic_domain(str(raw))
    else:
        resolved = default_semantic_domain()
    return {"global_active_domain": resolved}


# Top-level navigation areas (see docs/navigation-ia-proposal.md). Each area
# owns a set of URL prefixes (used to detect which area is "active" for the
# current request) and a submenu of quick links, rendered dynamically in the
# row below the main nav instead of one static global quicklinks list.
NAV_AREAS = [
    {
        "key": "data-sources",
        "prefixes": ["/data-sources/"],
        "submenu": [
            ("Übersicht", "/data-sources/", "Discovery- und Import-Übersicht aller Quellen (Markdown, PDF, OWL, Jira)."),
            ("Sources", "/data-sources/sources/", "Quellen-Registry der aktiven Domain."),
            ("Workspace", "/data-sources/workspace/", "Markdown-Dateien vor dem Import durchsuchen/prüfen."),
            ("PDF Import Jobs", "/data-sources/pdf/", "PDF-Batch-Import-Jobs und Verlauf."),
            ("Jira Domain Terms", "/data-sources/jira/domain-terms/", "Domain-Begriffe für den Jira-Import pflegen."),
            ("Jira Exclusions", "/data-sources/jira/exclusions/", "Ausschlusslisten für den Jira-Import."),
        ],
    },
    {
        "key": "internal-knowledge",
        "prefixes": ["/knowledge/"],
        "submenu": [
            ("Übersicht", "/knowledge/", "Verarbeitungs-Hub: Sources, Records, Artifacts."),
            ("Semantic Terms", "/knowledge/semantic/", "Semantische Begriffe, Domain-Analyse und Konzeptgraph."),
            ("Records", "/knowledge/records/", "Records der aktiven Domain durchsuchen."),
            ("Artifacts", "/knowledge/artifacts/", "Generierte Artefakte und Zusammenfassungen."),
            ("Jobs", "/knowledge/jobs/", "Hintergrund-Jobs und Sync-Verlauf."),
            ("Knowledge API", "/knowledge/api/", "Knowledge-API-Browser und Health-Checks."),
            ("Support Chat", "/knowledge/chat/support/", "Domänen-übergreifender Support-Chat."),
            ("Ollama Chat", "/knowledge/chat/ollama/", "Lokaler LLM-Chat für Ad-hoc-Fragen."),
        ],
    },
    {
        "key": "info-output",
        "prefixes": ["/output/"],
        "submenu": [
            ("Übersicht", "/output/", "Alle Ausgabeformate im Überblick."),
            ("Infosite Dashboard", "/output/infosite/dashboard/", "Projekte, Generierung und AI-Refinement."),
            ("Quiz (geplant)", "/output/quiz/", "Platzhalter für ein zukünftiges Quiz-Ausgabeformat — noch kein Konzept."),
        ],
    },
    {
        "key": "cms-catalog",
        "prefixes": ["/cms/", "/cms-admin/", "/cms-documents/"],
        "submenu": [
            ("Data Source Catalog", "/cms/data-sources/", "Editorial-Katalog der Datenquellen (Wagtail)."),
            ("Knowledge Block Catalog", "/cms/knowledge-blocks/", "Editorial-Katalog der extrahierten Wissensblöcke (Wagtail)."),
            ("Wagtail Admin", "/cms-admin/", "Wagtail-Administrationsoberfläche."),
        ],
    },
    {
        "key": "settings",
        "prefixes": ["/settings/"],
        "submenu": [
            ("Configuration", "/settings/config/", "Aktive AppConfig-Werte anzeigen."),
            ("Layout", "/settings/layout/", "GUI-Panelbreiten und Layout-Presets anpassen."),
        ],
    },
]


def nav_areas(request):
    """Determine the active top-level nav area (longest matching URL prefix
    wins) and expose all areas' submenus, so base.html can render a dynamic
    submenu row for whichever area is currently active."""
    path = request.path
    best_key = "dashboard"
    best_len = 0
    for area in NAV_AREAS:
        for prefix in area["prefixes"]:
            if path.startswith(prefix) and len(prefix) > best_len:
                best_key = area["key"]
                best_len = len(prefix)
    return {
        "nav_active_area": best_key,
        "nav_areas": NAV_AREAS,
    }
