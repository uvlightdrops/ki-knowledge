"""Versioned, framework-free immutable contribution envelopes (metadata, not files)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any

from .models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeRelationRecord, KnowledgeSource

VERSION = "knowledge.contribution/1"
DOMAIN_TAG = "contribution_domain"
PROVENANCE_KEY = "contribution"
# Deliberately bounded first wire profile, independent of legacy block subtypes.
OBJECT_TYPES = {"text", "image", "table", "audio", "video", "document", "code", "quiz"}


class ContributionConflict(ValueError):
    """An immutable revision or a reserved destination identity already exists."""


def digest(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("contribution must contain finite, UTF-8 JSON values") from exc


def identity(domain: str, origin: str, revision: str, kind: str, original_id: Any) -> str:
    return "contrib-v1-" + digest([domain, origin, revision, kind, original_id])


def _string(value: Any, field: str, *, empty: bool = False, limit: int | None = None) -> str:
    if not isinstance(value, str) or (not empty and (not value or value != value.strip())):
        raise ValueError(f"{field} must be a {'nonempty trimmed ' if not empty else ''}string")
    if "\x00" in value or (limit is not None and len(value) > limit):
        raise ValueError(f"{field} contains NUL or exceeds its length limit")
    return value


@dataclass(frozen=True)
class Contribution:
    domain: str
    origin_node_id: str
    revision: str
    digest: str
    sources: list[KnowledgeSource]
    records: list[KnowledgeBlockRecord]
    artifacts: list[KnowledgeArtifact]
    relations: list[KnowledgeRelationRecord]


def prepare_contribution(payload: Any) -> Contribution:
    """Validate the complete closed graph before producing any storage objects."""
    fields = {"version", "domain", "origin_node_id", "revision", "digest", "sources", "records", "artifacts", "relations"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("contribution fields missing or unknown")
    if payload["version"] != VERSION:
        raise ValueError("unsupported contribution version")
    domain = _string(payload["domain"], "domain", limit=100)
    if not re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", domain):
        raise ValueError("domain must be a canonical slug")
    origin = _string(payload["origin_node_id"], "origin_node_id", limit=120)
    revision = _string(payload["revision"], "revision", limit=120)
    expected_digest = digest({key: value for key, value in payload.items() if key != "digest"})
    if payload["digest"] != expected_digest:
        raise ValueError("contribution digest mismatch")

    classes = {"sources": KnowledgeSource, "records": KnowledgeBlockRecord,
               "artifacts": KnowledgeArtifact, "relations": KnowledgeRelationRecord}
    rows: dict[str, list[dict[str, Any]]] = {}
    for kind, cls in classes.items():
        items = payload[kind]
        if not isinstance(items, list):
            raise ValueError(f"{kind} must be a list")
        rows[kind] = []
        for item in items:
            if not isinstance(item, dict) or set(item) != set(cls.__dataclass_fields__):
                raise ValueError(f"invalid {kind} fields")
            row = deepcopy(item)
            for field, value in row.items():
                if field == "metadata":
                    if not isinstance(value, dict):
                        raise ValueError("metadata must be an object")
                    if PROVENANCE_KEY in value or DOMAIN_TAG in value:
                        raise ValueError("reserved contribution ownership metadata")
                    provenance = value.get("provenance", {})
                    if not isinstance(provenance, dict):
                        raise ValueError("provenance must be an object")
                    for owner in (value, provenance):
                        if "domain" in owner and owner["domain"] != domain:
                            raise ValueError("metadata belongs to another domain")
                        for key in ("origin_node_id", "node_id"):
                            if key in owner and owner[key] != origin:
                                raise ValueError("inconsistent origin ownership")
                    if "source_id" in value and value["source_id"] != row.get("source_id"):
                        raise ValueError("inconsistent source ownership")
                elif field in {"tags", "source_block_ids"}:
                    if not isinstance(value, list):
                        raise ValueError(f"{field} must be a list")
                    for entry in value:
                        _string(entry, field)
                elif field == "order_index":
                    if type(value) is not int:
                        raise ValueError("order_index must be an integer")
                elif field == "weight":
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError("weight must be finite numeric")
                elif field == "parent_block_id" and value is None:
                    pass
                else:
                    _string(value, field, empty=field in {"title", "content", "path", "location"})
            if kind == "records" and row["object_type"] not in OBJECT_TYPES:
                raise ValueError("unsupported object_type in contribution v1")
            rows[kind].append(row)
    if not rows["sources"]:
        raise ValueError("contribution needs at least one source")

    ids: dict[str, set[str]] = {}
    for kind, field in (("sources", "source_id"), ("records", "block_id"), ("artifacts", "artifact_id")):
        ids[kind] = {row[field] for row in rows[kind]}
        if len(ids[kind]) != len(rows[kind]):
            raise ValueError(f"duplicate {field}")
    edges = set()
    for row in rows["records"] + rows["artifacts"]:
        if row["source_id"] not in ids["sources"]:
            raise ValueError("unknown source_id")
        refs = row.get("source_block_ids", [])
        if row.get("parent_block_id") is not None:
            refs = [*refs, row["parent_block_id"]]
        if any(ref not in ids["records"] for ref in refs):
            raise ValueError("block reference outside contribution domain scope")
    for row in rows["relations"]:
        edge = (row["source_block_id"], row["target_block_id"], row["relation"])
        if edge in edges:
            raise ValueError("duplicate relation")
        edges.add(edge)
        if any(ref not in ids["records"] for ref in edge[:2]):
            raise ValueError("relation reference outside contribution domain scope")

    def mapped(kind: str, value: str) -> str:
        return identity(domain, origin, revision, kind, value)

    transformed: dict[str, list[Any]] = {}
    for kind, cls in classes.items():
        transformed[kind] = []
        for original in rows[kind]:
            row = deepcopy(original)
            id_field = {"sources": "source_id", "records": "block_id", "artifacts": "artifact_id"}.get(kind)
            original_id = original[id_field] if id_field else [
                original["source_block_id"], original["target_block_id"], original["relation"]]
            row["metadata"][DOMAIN_TAG] = domain
            row["metadata"][PROVENANCE_KEY] = {
                "origin_node_id": origin, "domain": domain, "revision": revision,
                "original_id": original_id, "digest": expected_digest,
                "original_refs": {key: original[key] for key in (
                    "source_id", "parent_block_id", "source_block_ids", "source_block_id", "target_block_id"
                ) if key in original},
            }
            if id_field:
                row[id_field] = mapped(kind, original[id_field])
            if kind == "sources":
                row["metadata"][PROVENANCE_KEY]["original_location"] = original["location"]
                # Store helpers also join/delete by location. Never alias a local
                # path or another origin's identically named document.
                row["location"] = "contribution:" + row["source_id"]
            if kind != "sources" and "source_id" in row:
                row["source_id"] = mapped("sources", original["source_id"])
            if row.get("parent_block_id") is not None:
                row["parent_block_id"] = mapped("records", row["parent_block_id"])
            if "source_block_ids" in row:
                row["source_block_ids"] = [mapped("records", ref) for ref in row["source_block_ids"]]
            if kind == "relations":
                for field in ("source_block_id", "target_block_id"):
                    row[field] = mapped("records", row[field])
            transformed[kind].append(cls(**row))
    return Contribution(domain, origin, revision, expected_digest, **transformed)


def export_contribution(store, *, domain: str, origin_node_id: str, revision: str,
                        source_ids: list[str]) -> dict[str, Any]:
    """Explicit source selection; never send imported contributions as locally owned."""
    if not source_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError("select nonempty unique source_ids")
    sources, records, artifacts = [], [], []
    for source_id in source_ids:
        source = store.get_source(source_id)
        if source is None:
            raise ValueError(f"unknown source: {source_id}")
        sources.append(asdict(source))
        for record in store.list_records(source_id=source_id):
            row = asdict(record)
            row["object_type"] = record.record_type
            records.append(row)
        artifacts.extend(asdict(item) for item in store.list_artifacts(source_id=source_id))
    relations = []
    for item in store.list_relations_for_blocks([row["block_id"] for row in records]):
        relations.append({key: item[key] for key in KnowledgeRelationRecord.__dataclass_fields__})
    payload = dict(version=VERSION, domain=domain, origin_node_id=origin_node_id, revision=revision,
                   sources=sources, records=records, artifacts=artifacts, relations=relations)
    payload["digest"] = digest(payload)
    prepare_contribution(payload)
    return payload
