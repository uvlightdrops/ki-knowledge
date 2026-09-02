"""CSV import for Jira issue dumps."""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from ki_knowledge.integrations.jira_client import JiraIssue


class JiraCSVImporter:
    """Import Jira issues from CSV exports."""

    _FIELD_ALIASES: dict[str, tuple[str, ...]] = {
        "key": (
            "issuekey",
            "issuekeyid",
            "issue key",
            "key",
            "id",
            "vorgangsschlussel",
            "vorgangsschlussel:",
        ),
        "summary": ("summary", "title", "issue summary", "zusammenfassung"),
        "description": ("description", "issue description", "beschreibung"),
        "status": ("status", "status name"),
        "issue_type": ("issue type", "issuetype", "type", "vorgangstyp"),
        "assignee": (
            "assignee",
            "assignee name",
            "assignee display name",
            "bearbeiter",
        ),
        "labels": ("labels", "label", "stichworter"),
        "created_at": ("created", "erstellt"),
        "updated_at": ("updated", "aktualisiert"),
    }

    @classmethod
    def from_csv(
        cls,
        csv_path: str,
        encoding: str = "utf-8-sig",
        delimiter: Optional[str] = None,
    ) -> list[JiraIssue]:
        """
        Load Jira issues from a CSV file.

        Args:
            csv_path: Path to Jira CSV export
            encoding: File encoding (default handles UTF-8 BOM)
            delimiter: Optional delimiter override

        Returns:
            List of JiraIssue objects
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with path.open("r", encoding=encoding, newline="") as fh:
            if delimiter:
                reader = csv.DictReader(fh, delimiter=delimiter)
            else:
                sample = fh.read(8192)
                fh.seek(0)
                dialect = cls._detect_dialect(sample)
                reader = csv.DictReader(fh, dialect=dialect)

            if not reader.fieldnames:
                return []

            header_map = cls._build_header_map(reader.fieldnames)
            issues: list[JiraIssue] = []

            for row in reader:
                issues.append(cls._row_to_issue(row, header_map))

            return issues

    @classmethod
    def _detect_dialect(cls, sample: str) -> csv.Dialect:
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            return csv.excel

    @classmethod
    def _build_header_map(cls, headers: list[str]) -> dict[str, str]:
        normalized_headers = {
            cls._normalize_header(header): header
            for header in headers
            if header is not None
        }
        mapped: dict[str, str] = {}

        for target, aliases in cls._FIELD_ALIASES.items():
            for alias in aliases:
                normalized_alias = cls._normalize_header(alias)
                header = normalized_headers.get(normalized_alias)
                if header:
                    mapped[target] = header
                    break

        return mapped

    @classmethod
    def _normalize_header(cls, value: str) -> str:
        ascii_value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return re.sub(r"[^a-z0-9]+", "", ascii_value.lower()).strip()

    @classmethod
    def _clean_value(cls, row: dict[str, str], header: Optional[str]) -> str:
        if not header:
            return ""
        value = row.get(header, "")
        return value.strip() if isinstance(value, str) else ""

    @classmethod
    def _parse_labels(cls, raw_labels: str) -> list[str]:
        if not raw_labels:
            return []
        parts = re.split(r"[;,]", raw_labels)
        return [label.strip() for label in parts if label.strip()]

    @classmethod
    def _row_to_issue(
        cls,
        row: dict[str, str],
        header_map: dict[str, str],
    ) -> JiraIssue:
        key = cls._clean_value(row, header_map.get("key"))
        summary = cls._clean_value(row, header_map.get("summary"))
        description = cls._clean_value(row, header_map.get("description"))
        status = cls._clean_value(row, header_map.get("status")) or "Unknown"
        issue_type = cls._clean_value(row, header_map.get("issue_type")) or "Unknown"
        assignee = cls._clean_value(row, header_map.get("assignee")) or None
        labels = cls._parse_labels(cls._clean_value(row, header_map.get("labels")))
        created_at = cls._parse_datetime(
            cls._clean_value(row, header_map.get("created_at"))
        )
        updated_at = cls._parse_datetime(
            cls._clean_value(row, header_map.get("updated_at"))
        )

        used_headers = set(header_map.values())
        text_fields = {
            header: value.strip()
            for header, value in row.items()
            if header
            and header not in used_headers
            and isinstance(value, str)
            and value.strip()
        }

        return JiraIssue(
            key=key or "(unknown-key)",
            summary=summary or "(no summary)",
            description=description or None,
            status=status,
            issue_type=issue_type,
            assignee=assignee,
            labels=labels,
            created_at=created_at,
            updated_at=updated_at,
            text_fields=text_fields,
        )

    @classmethod
    def _parse_datetime(cls, value: str) -> Optional[str]:
        if not value:
            return None

        for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).isoformat(timespec="minutes")
            except ValueError:
                continue
        return value
