"""JIRA client for fetching and managing issues."""

import requests
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class JiraIssue:
    """JIRA issue data model."""
    key: str
    summary: str
    description: Optional[str]
    status: str
    issue_type: str
    assignee: Optional[str]
    labels: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    text_fields: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "summary": self.summary,
            "description": self.description,
            "status": self.status,
            "issue_type": self.issue_type,
            "assignee": self.assignee,
            "labels": self.labels,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "text_fields": self.text_fields,
        }


class JiraClient:
    """Client for interacting with JIRA API."""
    
    def __init__(self, url: str, username: str, api_token: str, timeout: int = 30):
        """
        Initialize JIRA client.
        
        Args:
            url: JIRA base URL (e.g., https://jira.example.com)
            username: JIRA username
            api_token: JIRA API token
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.auth = (username, api_token)
        self.timeout = timeout
        self.headers = {"Accept": "application/json"}
    
    def get_issue(self, issue_key: str) -> JiraIssue:
        """
        Fetch single issue by key.
        
        Args:
            issue_key: Issue key (e.g., "PROJ-123")
        
        Returns:
            JiraIssue object
        
        Raises:
            requests.HTTPError: If issue not found or request fails
        """
        url = f"{self.url}/rest/api/3/issue/{issue_key}"
        response = requests.get(
            url,
            auth=self.auth,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        fields = data.get("fields", {})
        
        assignee_data = fields.get("assignee") or {}

        return JiraIssue(
            key=data.get("key"),
            summary=fields.get("summary"),
            description=fields.get("description"),
            status=fields.get("status", {}).get("name"),
            issue_type=fields.get("issuetype", {}).get("name"),
            assignee=assignee_data.get("displayName"),
            labels=fields.get("labels", []),
        )
    
    def get_issues_by_jql(self, jql: str, max_results: int = 50) -> List[JiraIssue]:
        """
        Fetch issues using JQL query.
        
        Args:
            jql: JQL query string
            max_results: Maximum number of results
        
        Returns:
            List of JiraIssue objects
        
        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.url}/rest/api/3/search"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "description", "status", "issuetype", "assignee", "labels"]
        }
        
        response = requests.get(
            url,
            auth=self.auth,
            headers=self.headers,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        issues = []
        for item in response.json().get("issues", []):
            fields = item.get("fields", {})
            assignee_data = fields.get("assignee") or {}
            issues.append(JiraIssue(
                key=item.get("key"),
                summary=fields.get("summary"),
                description=fields.get("description"),
                status=fields.get("status", {}).get("name"),
                issue_type=fields.get("issuetype", {}).get("name"),
                assignee=assignee_data.get("displayName"),
                labels=fields.get("labels", []),
            ))
        
        return issues
