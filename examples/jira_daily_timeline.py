"""Build daily Jira timeline summaries from CSV with structured cache."""

from pathlib import Path
import sys
import os

# Allow direct execution via "python examples/jira_daily_timeline.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_core.config import Config


def build_daily_timeline() -> None:
    Config.from_env()  # Loads .env for local execution.
    csv_path = os.getenv("JIRA_CSV_PATH", "").strip()
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = os.getenv("JIRA_CACHE_DB", str(PROJECT_ROOT / ".jira_cache.sqlite")).strip()
    limit_days = int(os.getenv("JIRA_TIMELINE_DAYS", "14"))

    if not csv_path:
        print("CSV path missing in environment variables!")
        print("Set: JIRA_CSV_PATH=/path/to/jira-export.csv")
        return

    issues = JiraCSVImporter.from_csv(
        csv_path,
        encoding=csv_encoding,
        delimiter=csv_delimiter,
    )
    if not issues:
        print("No issues found in CSV.")
        return

    cache = JiraIssueCache(cache_db)
    imported = cache.ingest_issues(issues)
    timeline = cache.daily_timeline(limit_days=limit_days)

    print(f"Imported/updated issues: {imported}")
    print(f"Cache DB: {cache_db}")
    print(f"Showing last {limit_days} days\n")

    for day in timeline:
        issue_keys = ", ".join(day.issue_keys[:12])
        topic_line = ", ".join(day.topics) if day.topics else "(keine Themen erkannt)"
        print(f"{day.day} | issues: {day.issue_count} | themen: {topic_line}")
        print(f"  keys: {issue_keys}")


if __name__ == "__main__":
    build_daily_timeline()
