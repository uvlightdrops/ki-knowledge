"""Tests for Phase-A convergence contracts between kicli and iasem."""

from pathlib import Path

from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.markdown_blocks import MarkdownBlockParser
from ki_knowledge.knowledge.adapters import IasemQuizAdapter, JiraKnowledgeAdapter, MarkdownKnowledgeAdapter
from ki_knowledge.knowledge.models import KnowledgeSource


def test_markdown_adapter_maps_blocks_into_shared_records(tmp_path: Path):
    source = tmp_path / "notes.md"
    source.write_text("# Intro\n\nHallo Welt\n", encoding="utf-8")

    blocks = MarkdownBlockParser().parse_markdown(source.read_text(encoding="utf-8"), str(source))
    records = MarkdownKnowledgeAdapter.to_records(
        blocks,
        KnowledgeSource(
            source_id="md:notes",
            source_type="markdown",
            title="notes",
            location=str(source),
        ),
    )

    assert len(records) == len(blocks)
    assert any(record.block_type == "heading" for record in records)
    assert any("Hallo Welt" in record.content for record in records)


def test_jira_adapter_exposes_summary_description_and_text_fields():
    issue = JiraIssue(
        key="AE-1",
        summary="Login problem",
        description="Users cannot log in",
        status="Open",
        issue_type="Bug",
        assignee="ops@example.com",
        labels=["auth"],
        text_fields={"analysis": "Likely session timeout regression"},
    )
    records = JiraKnowledgeAdapter.to_records(
        issue,
        KnowledgeSource(
            source_id="jira:AE-1",
            source_type="jira_issue",
            title="AE-1",
            location="jira://AE-1",
        ),
    )

    assert [record.block_type for record in records] == [
        "issue_summary",
        "issue_description",
        "issue_text_field",
    ]


def test_iasem_quiz_adapter_normalizes_quiz_payload():
    payload = {
        "quiz": {
            "id": "care-1",
            "title": "Awareness Basics",
            "description": "Grundlagen",
            "sections": [
                {
                    "title": "Deeskalation",
                    "summary": "Ruhig bleiben",
                    "sameAs": "wd:Q5249216",
                    "kerninhalte": ["Beobachten", "Abstand halten"],
                }
            ],
            "questions": [
                {
                    "id": "q1",
                    "question": "Was hilft zuerst?",
                    "explanation": "Ruhe schafft Überblick.",
                    "sameAs": "wd:Q5249216",
                    "options": [
                        {"id": "A", "text": "Panik"},
                        {"id": "B", "text": "Deeskalation"},
                    ],
                    "correct_option_id": "B",
                }
            ],
        }
    }

    quiz = IasemQuizAdapter.to_quiz_module(payload)

    assert quiz.module_id == "care-1"
    assert quiz.question_count() == 1
    assert quiz.questions[0].correct_option_id == "B"
    assert quiz.knowledge_blocks[0]["same_as"] == "wd:Q5249216"


def test_iasem_quiz_adapter_supports_legacy_schulungsmodul_shape():
    payload = {
        "id": "legacy-1",
        "title": "Legacy Quiz",
        "data": {
            "SchulungsModul": {
                "id": "legacy-1",
                "titel": "Legacy Quiz",
                "beschreibung": "Altes Format",
                "kernkonzepte": [
                    {
                        "begriff": "Awareness",
                        "definition": "Aufmerksamkeit für Grenzen.",
                        "dimensionen": ["Grenzen respektieren"],
                        "sameAs": "wd:Q72813155",
                    }
                ],
                "quiz_fragen": [
                    {
                        "frage_text": "Was ist wichtig?",
                        "antwort_optionen": [
                            {"option_id": "A", "option_text": "Achtsamkeit"},
                            {"option_id": "B", "option_text": "Ignorieren"},
                        ],
                        "korrekte_antwort_id": "A",
                    }
                ],
            }
        },
    }

    quiz = IasemQuizAdapter.to_quiz_module(payload)

    assert quiz.module_id == "legacy-1"
    assert quiz.question_count() == 1
    assert quiz.knowledge_blocks[0]["title"] == "Awareness"
