"""Explicit status mapping between canonical sync/import status strings and
Wagtail's structured page-workflow states.

This directly addresses the gap documented in docs/content-model-matrix.md
Section 4 ("Statusmodell-Mapping"): the canonical status values
(`discovered`, `synced`, `imported`, `failed`) are free-form strings owned by
the legacy models (`InfoSiteProject.sync_status`, `SourceDocument.import_status`),
while Wagtail pages have their own structured workflow
(`draft` -> `in_review` -> `approved`/`rejected` -> `published`, backed by
`Page.live`, `Revision`, `WorkflowState`). The two models are **not
isomorphic** — this module makes that explicit instead of pretending a 1:1
mapping exists, so a future real cutover has a documented, inspectable
starting point rather than an implicit assumption baked into scattered code.

This is intentionally a *read-only, advisory* mapping today: calling
`describe_wagtail_equivalent()` does not change any Wagtail workflow state.
It exists to surface the mapping (and its gaps) directly in the UI, and to
give a single place to evolve the mapping if/when a real cutover is planned.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WagtailStatusEquivalence:
    """Describes how well (if at all) a canonical status maps onto Wagtail workflow."""

    canonical_status: str
    wagtail_equivalent: str
    quality: str  # "none", "approximate", "exact"
    note: str


# Mirrors docs/content-model-matrix.md Section 4 exactly; keep both in sync
# if this mapping is revised.
_STATUS_MAP: dict[str, WagtailStatusEquivalence] = {
    "discovered": WagtailStatusEquivalence(
        canonical_status="discovered",
        wagtail_equivalent="(none)",
        quality="none",
        note="Wagtail only knows 'a Page exists' or not; there's no concept of "
        "'a file was found on disk but nothing was created yet'.",
    ),
    "synced": WagtailStatusEquivalence(
        canonical_status="synced",
        wagtail_equivalent="(none)",
        quality="none",
        note="No Wagtail equivalent; this is a filesystem/DB sync state, not an editorial state.",
    ),
    "imported": WagtailStatusEquivalence(
        canonical_status="imported",
        wagtail_equivalent="live=True (published)",
        quality="approximate",
        note="Rough approximation only: 'imported' describes the source document, "
        "'live' describes the *editorial page*, which may not exist 1:1 per document "
        "(see matrix Section 2 - no per-document Wagtail page today).",
    ),
    "failed": WagtailStatusEquivalence(
        canonical_status="failed",
        wagtail_equivalent="(none)",
        quality="none",
        note="Wagtail pages have no error state; a failed sync/import has no page-level "
        "representation at all.",
    ),
}


def describe_wagtail_equivalent(canonical_status: str) -> WagtailStatusEquivalence:
    """Return the documented (advisory, non-authoritative) Wagtail equivalence
    for a canonical status string, or a 'none' entry if the status is unknown.
    """
    return _STATUS_MAP.get(
        canonical_status,
        WagtailStatusEquivalence(
            canonical_status=canonical_status,
            wagtail_equivalent="(none)",
            quality="none",
            note="Unrecognized canonical status; no mapping has been documented for it yet.",
        ),
    )


def all_mappings() -> list[WagtailStatusEquivalence]:
    """Return every documented mapping, in a stable order, for display purposes
    (e.g. an admin/editorial panel that wants to show the whole table).
    """
    return list(_STATUS_MAP.values())
