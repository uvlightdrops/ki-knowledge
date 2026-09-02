"""Issue processing with KI."""

from typing import Optional
from ki_knowledge.client import KIClient
from ki_knowledge.integrations.jira_client import JiraIssue


class IssueProcessor:
    """Process JIRA issues with KI."""
    
    def __init__(self, ki_client: KIClient):
        """
        Initialize processor.
        
        Args:
            ki_client: KIClient instance for AI operations
        """
        self.ki = ki_client

    def _additional_text_context(self, issue: JiraIssue) -> str:
        if not issue.text_fields:
            return ""

        lines = [
            f"- {name}: {value}"
            for name, value in issue.text_fields.items()
        ]
        return "\nZusätzliche benannte Felder:\n" + "\n".join(lines)
    
    def summarize_issue(self, issue: JiraIssue) -> str:
        """
        Generate concise summary of issue.
        
        Args:
            issue: JiraIssue object
        
        Returns:
            AI-generated summary
        """
        prompt = f"""Fasse das folgende JIRA-Issue in 1-2 Sätzen prägnant zusammen:

Key: {issue.key}
Type: {issue.issue_type}
Status: {issue.status}
Summary: {issue.summary}
Description: {issue.description or '(keine Beschreibung)'}
{self._additional_text_context(issue)}

Zusammenfassung:"""
        
        return self.ki.chat([{"role": "user", "content": prompt}]).strip()
    
    def extract_tasks(self, issue: JiraIssue) -> list[str]:
        """
        Extract actionable tasks from issue description.
        
        Args:
            issue: JiraIssue object
        
        Returns:
            List of task strings
        """
        if not issue.description:
            return []
        
        prompt = f"""Extrahiere alle konkreten Aufgaben/TODOs aus dieser Issue-Beschreibung.
Gib nur eine Aufgabe pro Zeile aus, kurz und prägnant.

Issue: {issue.key}
Beschreibung:
{issue.description}
{self._additional_text_context(issue)}

Aufgaben:"""
        
        response = self.ki.chat([{"role": "user", "content": prompt}]).strip()
        return [line.strip() for line in response.split("\n") if line.strip()]
    
    def generate_acceptance_criteria(self, issue: JiraIssue) -> str:
        """
        Generate acceptance criteria for issue.
        
        Args:
            issue: JiraIssue object
        
        Returns:
            Formatted acceptance criteria
        """
        prompt = f"""Generiere konkrete Akzeptanzkriterien (AC) für diese Issue.
Format: "Given ... When ... Then ..."

Issue Key: {issue.key}
Summary: {issue.summary}
Type: {issue.issue_type}
Beschreibung: {issue.description or '(keine Beschreibung)'}
{self._additional_text_context(issue)}

Akzeptanzkriterien:"""
        
        return self.ki.chat([{"role": "user", "content": prompt}]).strip()
