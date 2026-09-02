"""Test JIRA client."""

import pytest
from unittest.mock import Mock, patch
from ki_knowledge.integrations.jira_client import JiraClient, JiraIssue


class TestJiraIssue:
    """Test JiraIssue model."""
    
    def test_issue_creation(self):
        """Test creating a JIRA issue."""
        issue = JiraIssue(
            key="PROJ-123",
            summary="Test Issue",
            description="Description",
            status="To Do",
            issue_type="Task",
            assignee="John Doe",
            labels=["urgent"]
        )
        
        assert issue.key == "PROJ-123"
        assert issue.summary == "Test Issue"
        assert issue.status == "To Do"
    
    def test_issue_to_dict(self):
        """Test converting issue to dict."""
        issue = JiraIssue(
            key="PROJ-123",
            summary="Test",
            description=None,
            status="Done",
            issue_type="Bug",
            assignee=None,
            labels=[]
        )
        
        result = issue.to_dict()
        assert result["key"] == "PROJ-123"
        assert result["description"] is None


@patch("ki_knowledge.integrations.jira_client.requests.get")
def test_jira_client_get_issue(mock_get):
    """Test fetching single issue."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "key": "PROJ-123",
        "fields": {
            "summary": "Test Issue",
            "description": "Description",
            "status": {"name": "To Do"},
            "issuetype": {"name": "Task"},
            "assignee": {"displayName": "John"},
            "labels": ["urgent"]
        }
    }
    mock_get.return_value = mock_response
    
    client = JiraClient("https://jira.example.com", "user", "token")
    issue = client.get_issue("PROJ-123")
    
    assert issue.key == "PROJ-123"
    assert issue.summary == "Test Issue"
    mock_get.assert_called_once()


@patch("ki_knowledge.integrations.jira_client.requests.get")
def test_jira_client_get_issues_by_jql(mock_get):
    """Test fetching issues by JQL."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "issues": [
            {
                "key": "PROJ-1",
                "fields": {
                    "summary": "Issue 1",
                    "description": "Desc 1",
                    "status": {"name": "To Do"},
                    "issuetype": {"name": "Task"},
                    "assignee": None,
                    "labels": []
                }
            }
        ]
    }
    mock_get.return_value = mock_response
    
    client = JiraClient("https://jira.example.com", "user", "token")
    issues = client.get_issues_by_jql("status = 'To Do'")
    
    assert len(issues) == 1
    assert issues[0].key == "PROJ-1"
