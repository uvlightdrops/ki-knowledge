"""Test issue processor."""

import pytest
from unittest.mock import Mock, patch
from ki_knowledge.integrations.issue_processor import IssueProcessor
from ki_knowledge.integrations.jira_client import JiraIssue


@patch("ki_knowledge.integrations.issue_processor.KIClient")
def test_summarize_issue(mock_ki_client):
    """Test issue summarization."""
    mock_client = Mock()
    mock_client.chat.return_value = "Summary: Important issue"
    
    processor = IssueProcessor(mock_client)
    issue = JiraIssue(
        key="PROJ-1",
        summary="Test",
        description="Long description",
        status="To Do",
        issue_type="Task",
        assignee=None,
        labels=[]
    )
    
    result = processor.summarize_issue(issue)
    
    assert result == "Summary: Important issue"
    mock_client.chat.assert_called_once()
    called_prompt = mock_client.chat.call_args[0][0][0]["content"]
    assert "Zusätzliche benannte Felder" not in called_prompt


@patch("ki_knowledge.integrations.issue_processor.KIClient")
def test_extract_tasks(mock_ki_client):
    """Test task extraction."""
    mock_client = Mock()
    mock_client.chat.return_value = "Task 1\nTask 2\nTask 3"
    
    processor = IssueProcessor(mock_client)
    issue = JiraIssue(
        key="PROJ-1",
        summary="Test",
        description="Do X, Y, and Z",
        status="To Do",
        issue_type="Task",
        assignee=None,
        labels=[]
    )
    
    tasks = processor.extract_tasks(issue)
    
    assert len(tasks) == 3
    assert "Task 1" in tasks


@patch("ki_knowledge.integrations.issue_processor.KIClient")
def test_extract_tasks_empty_description(mock_ki_client):
    """Test task extraction with empty description."""
    mock_client = Mock()
    processor = IssueProcessor(mock_client)
    
    issue = JiraIssue(
        key="PROJ-1",
        summary="Test",
        description=None,
        status="To Do",
        issue_type="Task",
        assignee=None,
        labels=[]
    )
    
    tasks = processor.extract_tasks(issue)
    
    assert tasks == []
    mock_client.chat.assert_not_called()


@patch("ki_knowledge.integrations.issue_processor.KIClient")
def test_summarize_issue_includes_named_text_fields(mock_ki_client):
    """Test prompt includes additional named CSV text fields."""
    mock_client = Mock()
    mock_client.chat.return_value = "Summary"

    processor = IssueProcessor(mock_client)
    issue = JiraIssue(
        key="PROJ-2",
        summary="CSV-based issue",
        description="Main description",
        status="In Progress",
        issue_type="Story",
        assignee="Jane",
        labels=["backend"],
        text_fields={
            "Customfeld A": "Langer Freitext",
            "Customfeld B": "Noch mehr Kontext",
        },
    )

    processor.summarize_issue(issue)

    called_prompt = mock_client.chat.call_args[0][0][0]["content"]
    assert "Zusätzliche benannte Felder" in called_prompt
    assert "Customfeld A: Langer Freitext" in called_prompt
