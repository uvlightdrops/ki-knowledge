"""Tests for Jira CSV import."""

from pathlib import Path

from ki_knowledge.integrations.jira_csv import JiraCSVImporter


def test_import_jira_csv_with_named_text_fields(tmp_path: Path):
    csv_content = (
        "Issue key,Summary,Description,Status,Issue Type,Assignee,Labels,Custom Text,Acceptance Notes\n"
        "PROJ-1,CSV issue,\"Line 1\\nLine 2\",To Do,Task,Max Mustermann,\"bug,urgent\",Extra Kontext,\"Given A When B Then C\"\n"
    )
    csv_file = tmp_path / "jira.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    issues = JiraCSVImporter.from_csv(str(csv_file))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.key == "PROJ-1"
    assert issue.summary == "CSV issue"
    assert issue.description == "Line 1\\nLine 2"
    assert issue.status == "To Do"
    assert issue.issue_type == "Task"
    assert issue.assignee == "Max Mustermann"
    assert issue.labels == ["bug", "urgent"]
    assert issue.text_fields["Custom Text"] == "Extra Kontext"
    assert issue.text_fields["Acceptance Notes"] == "Given A When B Then C"


def test_import_jira_csv_with_semicolon_delimiter(tmp_path: Path):
    csv_content = (
        "Issue key;Summary;Description;Status;Issue Type;Assignee;Labels\n"
        "PROJ-2;Semicolon issue;Desc;Done;Bug;Alice;\"bug;high\"\n"
    )
    csv_file = tmp_path / "jira_semicolon.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    issues = JiraCSVImporter.from_csv(str(csv_file), delimiter=";")

    assert len(issues) == 1
    issue = issues[0]
    assert issue.key == "PROJ-2"
    assert issue.summary == "Semicolon issue"
    assert issue.labels == ["bug", "high"]


def test_import_jira_csv_with_german_headers(tmp_path: Path):
    csv_content = (
        "Zusammenfassung,Vorgangsschlüssel:,Vorgangstyp,Status,Bearbeiter,Beschreibung,Stichwörter,Erstellt,Aktualisiert\n"
        "Splunk etablieren,AE-1200,Aufgabe,Zu erledigen,max@example.com,Textfeld,betrieb;monitoring,23.10.2024 11:02,16.02.2026 11:12\n"
    )
    csv_file = tmp_path / "jira_de.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    issues = JiraCSVImporter.from_csv(str(csv_file))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.key == "AE-1200"
    assert issue.summary == "Splunk etablieren"
    assert issue.issue_type == "Aufgabe"
    assert issue.status == "Zu erledigen"
    assert issue.assignee == "max@example.com"
    assert issue.description == "Textfeld"
    assert issue.labels == ["betrieb", "monitoring"]
    assert issue.created_at == "2024-10-23T11:02"
    assert issue.updated_at == "2026-02-16T11:12"
