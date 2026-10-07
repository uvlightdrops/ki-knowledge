from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse

from widgetkit_django.layout_targets import PageTarget


_AREAS = [
    {
        "key": "dashboard", "nav_key": "dashboard", "prefixes": ["/"],
        "submenu": [
            ("Overview", "/", "Zentrale Startseite des Arbeitsbereichs."),
        ],
        "targets": [("overview", "Overview", "/")],
    },
    {
        "key": "datasources", "nav_key": "data-sources", "prefixes": ["/data-sources/"],
        "submenu": [
            ("Übersicht", "/data-sources/", "Discovery- und Import-Übersicht aller Quellen (Markdown, PDF, OWL, Jira)."),
            ("Sources", "/data-sources/sources/", "Quellen-Registry der aktiven Domain."),
            ("Workspace", "/data-sources/workspace/", "Quellen vor dem Import prüfen, vorbereiten und importieren."),
            ("PDF Import Jobs", "/data-sources/pdf/", "PDF-Batch-Import-Jobs und Verlauf."),
        ],
        "targets": [
            ("overview", "Übersicht", "/data-sources/"),
            ("sources", "Sources", "/data-sources/sources/"),
            ("workspace", "Workspace", "/data-sources/workspace/"),
            ("pdf", "PDF Import Jobs", "/data-sources/pdf/"),
        ],
    },
    {
        "key": "knowledge", "nav_key": "internal-knowledge", "prefixes": ["/knowledge/"],
        "submenu": [
            ("Übersicht", "/knowledge/", "Verarbeitungs-Hub: Sources, Records, Artifacts."),
            ("Semantic Layer", "/knowledge/semantic/", "Semantische Begriffe, Domain-Analyse und Konzeptgraph."),
            ("Domain Terms", "/knowledge/semantic/terms/", "Interne Begriffsliste zur Wissensmodellierung und Domain-Analyse."),
            ("Exclusion List", "/knowledge/semantic/", "Generische Stopword-/Ausschlussliste für Vorverarbeitung und Filterung."),
            ("Records", "/knowledge/records/", "Records der aktiven Domain durchsuchen."),
            ("Artifacts", "/knowledge/artifacts/", "Generierte Artefakte und Zusammenfassungen."),
            ("Jobs", "/knowledge/jobs/", "Hintergrund-Jobs und Sync-Verlauf."),
            ("Knowledge API", "/knowledge/api/", "Knowledge-API-Browser und Health-Checks."),
            ("Support Chat", "/knowledge/chat/support/", "Domänen-übergreifender Support-Chat."),
            ("Ollama Chat", "/knowledge/chat/ollama/", "Lokaler LLM-Chat für Ad-hoc-Fragen."),
        ],
        "targets": [
            ("overview", "Übersicht", "/knowledge/"),
            ("semantic", "Semantic Layer", "/knowledge/semantic/"),
            ("terms", "Domain Terms", "/knowledge/semantic/terms/"),
            ("semantic-exclusions", "Exclusion List", "/knowledge/semantic/"),
            ("records", "Records", "/knowledge/records/"),
            ("artifacts", "Artifacts", "/knowledge/artifacts/"),
            ("jobs", "Jobs", "/knowledge/jobs/"),
            ("api", "Knowledge API", "/knowledge/api/"),
            ("support-chat", "Support Chat", "/knowledge/chat/support/"),
            ("ollama-chat", "Ollama Chat", "/knowledge/chat/ollama/"),
        ],
    },
    {
        "key": "infooutput", "nav_key": "info-output", "prefixes": ["/output/"],
        "submenu": [
            ("Übersicht", "/output/", "Alle Ausgabeformate im Überblick."),
            ("Infosite Dashboard", "/output/infosite/dashboard/", "Projekte, Generierung und AI-Refinement."),
            ("Quiz (geplant)", "/output/quiz/", "Platzhalter für ein zukünftiges Quiz-Ausgabeformat — noch kein Konzept."),
        ],
        "targets": [
            ("overview", "Übersicht", "/output/"),
            ("infosite-dashboard", "Infosite Dashboard", "/output/infosite/dashboard/"),
            ("quiz", "Quiz (geplant)", "/output/quiz/"),
        ],
    },
    {
        "key": "admin", "nav_key": "admin", "prefixes": ["/admin-overview/"],
        "submenu": [
            ("Übersicht", "/admin-overview/", "Zentrale Admin-Übersicht über Domains, Status und Systemwerte."),
            ("Domain Management", "/admin-overview/domains/", "Domains anlegen, Datenverzeichnisse scannen und verwalten."),
            ("Distributed Sync", "/admin-overview/sync/", "Node-Konfiguration, Master-Katalog und Sync-Historie verwalten."),
            ("System Status", "/admin-overview/status/", "Anwendungsstatus und Laufzeitwerte prüfen."),
        ],
        "targets": [
            ("overview", "Übersicht", "/admin-overview/"),
            ("domains", "Domain Management", "/admin-overview/domains/"),
            ("sync", "Distributed Sync", "/admin-overview/sync/"),
            ("status", "System Status", "/admin-overview/status/"),
        ],
    },
    {
        "key": "settings", "nav_key": "settings", "prefixes": ["/settings/"],
        "submenu": [
            ("Übersicht", "/settings/", "Settings overview."),
            ("Configuration", "/settings/config/", "Aktive AppConfig-Werte anzeigen."),
            ("Builder", "/settings/layout/builder/", "Widget-Layout pro Area verwalten."),
            ("Widget catalog", "/settings/layout/widgets/", "Preview aller Widgets und ihres HTML-Codes."),
            ("Widget shell builder", "/settings/layout/shell-builder/", "Widget-Shells ohne Live-Daten zusammenklicken."),
            ("Widget shell overview table", "/settings/layout/shells/", "Tabellarische Übersicht aller gespeicherten Widget-Shells."),
        ],
        "targets": [
            ("overview", "Übersicht", "/settings/"),
            ("config", "Configuration", "/settings/config/"),
            ("builder", "Builder", "/settings/layout/builder/"),
            ("widgets", "Widget catalog", "/settings/layout/widgets/"),
            ("shell-builder", "Widget shell builder", "/settings/layout/shell-builder/"),
            ("shells", "Widget shell overview table", "/settings/layout/shells/"),
        ],
    },
]

_ACTIONS = [
    {
        "key": "cms-catalog", "nav_key": "cms-catalog",
        "prefixes": ["/cms/", "/cms-admin/", "/cms-documents/"],
        "submenu": [
            ("Data Source Catalog", "/cms/data-sources/", "Editorial-Katalog der Datenquellen (Wagtail)."),
            ("Knowledge Block Catalog", "/cms/knowledge-blocks/", "Editorial-Katalog der extrahierten Wissensblöcke (Wagtail)."),
            ("Wagtail Admin", "/cms-admin/", "Wagtail-Administrationsoberfläche."),
        ],
    },
    {
        "key": "layout-builder", "nav_key": "layout-builder",
        "prefixes": ["/settings/layout/builder/", "/settings/layout/widgets/", "/settings/layout/shells/"],
        "submenu_source": "settings",
    },
]


def layout_targets_for_area(area_key: str) -> list[PageTarget]:
    normalized = (area_key or "dashboard").strip().lower()
    area = next((item for item in _AREAS if item["key"] == normalized), None)
    if area is None:
        return [PageTarget("overview", "Overview", "/")]
    return [
        PageTarget(key, label, path)
        for key, label, path in area["targets"]
        if key not in {"builder", "widgets", "shell-builder"}
    ]


def layout_target(area_key: str, subpage_key: str) -> PageTarget:
    targets = layout_targets_for_area(area_key)
    return next((item for item in targets if item.key == (subpage_key or "overview").strip().lower()), targets[0])


def layout_builder_url(area_key: str, subpage_key: str = "overview") -> str:
    return f"{reverse('settings-layout-builder')}?{urlencode({'area': area_key, 'subpage': subpage_key})}"


def nav_areas_config() -> list[dict[str, object]]:
    areas = [
        {
            "key": item["nav_key"],
            "prefixes": list(item["prefixes"]),
            "submenu": [(label, path, description) for label, path, description in item["submenu"]],
        }
        for item in _AREAS
    ]
    for action in _ACTIONS:
        source = next(item for item in _AREAS if item["key"] == "settings") if action.get("submenu_source") else None
        submenu = source["submenu"] if source else action["submenu"]
        areas.append({
            "key": action["nav_key"],
            "prefixes": list(action["prefixes"]),
            "submenu": [(label, path, description) for label, path, description in submenu],
        })
    return areas
