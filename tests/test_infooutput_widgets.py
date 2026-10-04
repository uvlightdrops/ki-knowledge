from types import SimpleNamespace

from ki_knowledge.django_site.dashboard_registry import default_widget_ids_for_area
from ki_knowledge.django_site.page_widgets import build_output_widget_cards


def test_infooutput_widgets_render_data_instead_of_description_placeholders():
    project = SimpleNamespace(
        id=4,
        title="Human Design",
        domain="human-design",
        working_title="gates",
        generation_status="completed",
    )
    document = SimpleNamespace(
        project=project,
        project_id=project.id,
        display_path="output/gates.md",
        review_status="approved",
        get_review_status_display=lambda: "Freigegeben",
    )

    cards = build_output_widget_cards(
        active_domain="human-design",
        domain_stats=[
            {
                "slug": "human-design",
                "display_name": "Human Design",
                "total": 3,
                "none": 1,
                "in_review": 1,
                "approved": 1,
                "rejected": 0,
            }
        ],
        domain_documents=[document],
        recent_projects=[project],
        formats=[
            {
                "label": "Infosite",
                "url": "/output/infosite/dashboard/",
                "status": "aktiv",
                "description": "Ausgabe aus Wissen erstellen.",
            }
        ],
        widget_ids=default_widget_ids_for_area("infooutput"),
    )

    assert len(cards) == 6
    for card in cards:
        assert card["body"].strip()
        assert card["description"] not in card["body"]
    assert "Infosite" in cards[0]["body"]
    assert "human-design" in cards[1]["body"]
    assert "Human Design" in cards[2]["body"]
    assert "Human Design" in cards[3]["body"]
    assert "output/gates.md" in cards[4]["body"]
    assert "output/gates.md" in cards[5]["body"]
