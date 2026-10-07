import pytest
from django.template.loader import render_to_string


@pytest.mark.parametrize("template_name", [
    "infosite/dashboard.html",
    "kicli_django/admin_domain_management.html",
    "kicli_django/admin_system_status.html",
    "kicli_django/semantic_landing.html",
    "kicli_django/output_quiz.html",
])
def test_widget_pages_use_twelve_column_widget_grid(template_name):
    html = render_to_string(template_name, {
        "widget_cards": [
            {"label": "Wide widget", "width": 8, "body": ""},
            {"label": "Narrow widget", "width": 4, "body": ""},
        ],
    })

    assert '<div class="widget-grid">' in html
    assert "grid-column: span 8;" in html
    assert "grid-column: span 4;" in html
    assert '<div class="grid">' not in html
