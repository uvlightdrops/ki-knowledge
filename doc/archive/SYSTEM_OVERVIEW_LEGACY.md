---
project: "ki-knowledge"
scope: "architecture"
created: "2026-11-05 13"
updated: "2026-11-05 13"
update_reason: "Extract legacy data layouts and migration notes from System Overview"
status: "archived"
agent_project: "ki-knowledge"
---

# Legacy System Overview: data layouts

Reference for existing installations, not the layout for new deployments.
The [System Overview](../architecture/SYSTEM_OVERVIEW.md#data-layout-resolver)
documents the current layout and CLI path inspection.

## Version markers and upgrades

The current resolver defaults to v3 when `<data_root>/.layout-version` is
missing. Previously, a missing marker meant v1. Before installing that change
on an existing unmarked v1 root, explicitly preserve its version:

```bash
# Example for the confirmed v1 root on U7; run before updating/restarting.
printf '1\n' > /home/kraizy7/ki/data/ki-knowledge/.layout-version
```

Only do this after confirming that the root really uses v1 and has no marker.
Do not overwrite an existing marker. A v2 root must declare `2`.
Changing or removing the marker does not move files or rewrite stored paths.
Do not switch an existing root to v3 merely by editing this file.

## v1: source type first

Paths are relative to the data root:

| Path | Content |
|---|---|
| `md/<domain>/` | Markdown sources |
| `pdf/<domain>/` | PDF originals |
| `epub/<domain>/` | EPUB originals |
| `jira/<domain>/` | Jira CSVs and per-domain derived databases |
| `owl/<domain>/` | Ontology sources |
| `mix/<domain>/` | Mixed sources |
| `data_out/<domain>/` | Generated output |
| Root-level database files | Global state |

Pipeline jobs and the InfoSite block store also used `~/.ki-knowledge/`.
For example, `md/anthro-ag/` denotes domain `anthro-ag`, not domain `md`.

## v2: nested domain roots

Sources reside under `domains/<domain>/sources/{md,pdf,epub,jira,owl,mix}/`.
Per-domain `derived/` and `output/` are siblings of `sources/`.
Global databases are stored in `system/`.

## Migration to v3

From the checkout, with the appropriate stage selected:

```bash
KI_STAGE=prod-uberspace7 .venv/bin/python manage.py migrate_data_layout
```

This prints a read-only plan. `--target-version 2` selects the compatibility
layout. Applying requires `--apply --confirm-services-stopped` after all app
services and workers accessing these files have stopped, and a backup.

The planner blocks destination collisions, reserved domain names, unsafe
relative symlinks, external source-root/database overrides and non-SQLite
Django databases. In particular, this is **not a supported migration command
for the U7 PostgreSQL deployment**; do not bypass that guard.

For supported SQLite installations it rewrites stored paths in PDF jobs,
InfoSite records and the knowledge store (including JSON provenance), and
journals every executed step to `system/layout-migration.jsonl`.
