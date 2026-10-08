"""Tests for the v1 -> v2 data layout migration."""

import json
import sqlite3
from pathlib import Path

import pytest

from ki_knowledge.data_layout import MARKDOWN, PDF, DataLayout
from ki_knowledge.data_layout_migration import apply_plan, plan_migration, plan_v1_to_v2


@pytest.fixture
def v1_root(tmp_path):
    root = tmp_path / "data"
    home = tmp_path / "home" / ".ki-knowledge"
    cloud = tmp_path / "cloud" / "anthro"
    (cloud / "sstk").mkdir(parents=True)
    (cloud / "sstk" / "a.md").write_text("# A")

    (root / "md" / "human-design" / "prompt-library").mkdir(parents=True)
    (root / "md" / "human-design" / "prompt-library" / "p.md").write_text("p")
    (root / "md" / "anthro").symlink_to(cloud, target_is_directory=True)
    (root / "pdf" / "Anthro").mkdir(parents=True)
    (root / "pdf" / "Anthro" / "b.pdf").write_bytes(b"%PDF")
    (root / "pdf" / "default").mkdir()
    (root / "jira" / "human-design").mkdir(parents=True)
    (root / "jira" / "human-design" / "issues.csv").write_text("key\n")
    (root / "jira" / "human-design" / "cache.sqlite").write_bytes(b"")
    (root / "jira" / "human-design" / "jira_graph.sqlite").write_bytes(b"")
    (root / "owl" / "human-design").mkdir(parents=True)
    (root / "data_out" / "anthro" / "sstk").mkdir(parents=True)
    (root / "data_out" / "anthro" / "sstk" / "index.md").write_text("out")
    (root / "knowledge.db").write_bytes(b"")
    (root / "django.sqlite3").write_bytes(b"")

    with sqlite3.connect(root / ".pdf_import_jobs.sqlite") as conn:
        conn.execute("CREATE TABLE pdf_import_jobs (job_id TEXT, pdf_path TEXT, result_json TEXT)")
        conn.execute(
            "INSERT INTO pdf_import_jobs (job_id, pdf_path) VALUES ('1', ?)",
            (str(root / "pdf" / "Anthro" / "b.pdf"),),
        )
        conn.execute("INSERT INTO pdf_import_jobs (job_id, pdf_path) VALUES ('2', '/elsewhere/c.pdf')")
    home.mkdir(parents=True)
    (home / "pipeline_jobs.db").write_bytes(b"")
    return root, home, cloud


def test_plan_is_dry(v1_root):
    root, home, _ = v1_root
    before = sorted(str(p) for p in root.rglob("*"))

    plan = plan_v1_to_v2(root, home)

    assert plan.ok, plan.conflicts
    assert plan.db_rows_to_rewrite == {"pdf_import_jobs.pdf_path": 1}
    assert sorted(str(p) for p in root.rglob("*")) == before
    assert (home / "pipeline_jobs.db").exists()


def test_apply_moves_everything_domain_first(v1_root):
    root, home, cloud = v1_root

    result = apply_plan(plan_v1_to_v2(root, home))

    layout = DataLayout(root)
    assert layout.version == 2
    assert sorted(p.name for p in root.iterdir()) == [".layout-version", "domains", "system"]
    assert sorted(p.name for p in (root / "domains").iterdir()) == ["anthro", "default", "human-design"]

    md_link = layout.source_dir(MARKDOWN, "anthro")
    assert md_link.is_symlink() and md_link.resolve() == cloud.resolve()
    assert (cloud / "sstk" / "a.md").read_text() == "# A"
    assert layout.source_dir(PDF, "anthro", "b.pdf").exists()
    assert (layout.source_dir(MARKDOWN, "human-design", "prompt-library", "p.md")).read_text() == "p"
    assert layout.source_dir("jira", "human-design", "issues.csv").exists()
    assert (layout.domain_state_dir("human-design") / "cache.sqlite").exists()
    assert (layout.domain_state_dir("human-design") / "jira_graph.sqlite").exists()
    assert layout.source_dir("owl", "human-design").is_dir()
    assert layout.source_dir(PDF, "default").is_dir()
    assert (layout.output_dir("anthro", "sstk", "index.md")).read_text() == "out"
    for path in (layout.knowledge_db_path(), layout.django_db_path(), layout.pdf_jobs_db_path(), layout.pipeline_jobs_db_path()):
        assert path.exists(), path
    assert not home.exists()

    with sqlite3.connect(layout.pdf_jobs_db_path()) as conn:
        paths = dict(conn.execute("SELECT job_id, pdf_path FROM pdf_import_jobs"))
    assert paths == {"1": str(layout.source_dir(PDF, "anthro", "b.pdf")), "2": "/elsewhere/c.pdf"}
    assert result.db_rows_rewritten == {"pdf_import_jobs.pdf_path": 1}

    journal = [json.loads(line) for line in result.log_path.read_text().splitlines()]
    assert journal[-1]["kind"] == "write_version"
    assert any(entry["src"] == str(root / "md" / "anthro") for entry in journal)


def test_existing_target_aborts_without_changes(v1_root):
    root, home, _ = v1_root
    (root / "domains" / "anthro" / "sources" / "md").mkdir(parents=True)

    plan = plan_v1_to_v2(root, home)

    assert not plan.ok
    with pytest.raises(RuntimeError):
        apply_plan(plan)
    assert (root / "md" / "anthro").is_symlink()


def test_already_migrated_root_is_rejected(v1_root):
    root, home, _ = v1_root
    apply_plan(plan_v1_to_v2(root, home))

    plan = plan_v1_to_v2(root, home)

    assert not plan.ok
    assert "already uses layout v2" in plan.conflicts[0]


def test_relative_symlink_is_recreated_absolute(tmp_path):
    root = tmp_path / "data"
    (tmp_path / "shared" / "politik").mkdir(parents=True)
    (root / "md").mkdir(parents=True)
    (root / "md" / "politik").symlink_to(Path("..") / ".." / "shared" / "politik", target_is_directory=True)

    apply_plan(plan_v1_to_v2(root, tmp_path / "nohome"))

    link = DataLayout(root).source_dir(MARKDOWN, "politik")
    assert link.is_symlink()
    assert link.resolve() == (tmp_path / "shared" / "politik").resolve()


def test_v1_to_v3_moves_to_direct_domain_roots_and_rewrites_json_paths(v1_root):
    root, home, _ = v1_root
    old_source = root / "md" / "human-design" / "prompt-library" / "p.md"
    with sqlite3.connect(root / "knowledge.db") as conn:
        conn.execute("CREATE TABLE knowledge_sources (location TEXT, metadata_json TEXT)")
        conn.execute(
            "INSERT INTO knowledge_sources VALUES (?, ?)",
            (
                str(old_source),
                json.dumps({"provenance": {"source_path": str(old_source)}}),
            ),
        )
        conn.execute("CREATE TABLE knowledge_blocks (source_path TEXT, metadata_json TEXT)")
        conn.execute(
            "INSERT INTO knowledge_blocks VALUES (?, ?)",
            (str(old_source), json.dumps({"source_document": str(old_source)})),
        )
        conn.execute("CREATE TABLE knowledge_artifacts (content TEXT)")
        conn.execute(
            "INSERT INTO knowledge_artifacts VALUES (?)",
            (f"Imported from {old_source} for review.",),
        )
    with sqlite3.connect(home / "pipeline_jobs.db") as conn:
        conn.execute("CREATE TABLE distributed_sync_jobs (payload_json TEXT)")
        conn.execute(
            "INSERT INTO distributed_sync_jobs VALUES (?)",
            (json.dumps({"source_directory": str(old_source.parent)}),),
        )

    plan = plan_migration(root, home_state_dir=home)

    assert plan.ok, plan.conflicts
    assert plan.target_version == 3
    assert plan.db_rows_to_rewrite == {
        "knowledge_blocks.metadata_json": 1,
        "knowledge_blocks.source_path": 1,
        "knowledge_artifacts.content": 1,
        "knowledge_sources.location": 1,
        "knowledge_sources.metadata_json": 1,
        "pdf_import_jobs.pdf_path": 1,
        "distributed_sync_jobs.payload_json": 1,
    }
    result = apply_plan(plan)

    layout = DataLayout(root)
    assert layout.version == 3
    assert not (root / "domains").exists()
    assert not (root / "md").exists()
    assert (layout.source_dir(MARKDOWN, "human-design", "prompt-library", "p.md")).exists()
    assert (layout.source_dir(PDF, "anthro", "b.pdf")).exists()
    assert (layout.source_dir("jira", "human-design", "issues.csv")).exists()
    assert (layout.domain_state_dir("human-design") / "cache.sqlite").exists()
    assert (layout.output_dir("anthro", "sstk", "index.md")).exists()
    with sqlite3.connect(layout.knowledge_db_path()) as conn:
        source_path, metadata = conn.execute("SELECT location, metadata_json FROM knowledge_sources").fetchone()
        block_path, block_metadata = conn.execute("SELECT source_path, metadata_json FROM knowledge_blocks").fetchone()
    expected = str(layout.source_dir(MARKDOWN, "human-design", "prompt-library", "p.md"))
    assert source_path == expected and block_path == expected
    assert json.loads(metadata)["provenance"]["source_path"] == expected
    assert json.loads(block_metadata)["source_document"] == expected
    with sqlite3.connect(layout.knowledge_db_path()) as conn:
        artifact_content = conn.execute("SELECT content FROM knowledge_artifacts").fetchone()[0]
    assert artifact_content == f"Imported from {expected} for review."
    with sqlite3.connect(layout.pipeline_jobs_db_path()) as conn:
        sync_payload = json.loads(conn.execute("SELECT payload_json FROM distributed_sync_jobs").fetchone()[0])
    assert sync_payload["source_directory"] == str(layout.source_dir(MARKDOWN, "human-design", "prompt-library"))
    assert result.db_rows_rewritten == plan.db_rows_to_rewrite


def test_v2_to_v3_flattens_domain_sources_and_rewrites_paths(tmp_path):
    root = tmp_path / "data-v2"
    old_source = root / "domains" / "anthro" / "sources" / "md" / "book" / "a.md"
    old_source.parent.mkdir(parents=True)
    old_source.write_text("# A")
    (root / ".layout-version").write_text("2\n")
    (root / "domains" / "anthro" / "sources" / "pdf").mkdir()
    (root / "domains" / "anthro" / "derived").mkdir()
    (root / "domains" / "anthro" / "output").mkdir()
    (root / "system").mkdir()
    with sqlite3.connect(root / "system" / "knowledge.db") as conn:
        conn.execute("CREATE TABLE knowledge_blocks (source_path TEXT, metadata_json TEXT)")
        conn.execute("INSERT INTO knowledge_blocks VALUES (?, '{}')", (str(old_source),))

    plan = plan_migration(root)
    assert plan.ok, plan.conflicts
    assert plan.db_rows_to_rewrite == {"knowledge_blocks.source_path": 1}
    apply_plan(plan)

    layout = DataLayout(root)
    new_source = layout.source_dir(MARKDOWN, "anthro", "book", "a.md")
    assert layout.version == 3
    assert new_source.read_text() == "# A"
    assert (layout.source_dir(PDF, "anthro")).is_dir()
    assert (layout.domain_state_dir("anthro")).is_dir()
    assert layout.output_dir("anthro").is_dir()
    with sqlite3.connect(layout.knowledge_db_path()) as conn:
        assert conn.execute("SELECT source_path FROM knowledge_blocks").fetchone()[0] == str(new_source)


def test_migration_blocks_relative_links_that_escape_moved_tree(tmp_path):
    root = tmp_path / "data"
    tree = root / "md" / "anthro"
    tree.mkdir(parents=True)
    (root / "outside").mkdir()
    (tree / "external").symlink_to(Path("../../../outside"), target_is_directory=True)

    plan = plan_migration(root)

    assert not plan.ok
    assert any("escapes moved tree" in conflict for conflict in plan.conflicts)
    with pytest.raises(RuntimeError, match="conflicts"):
        apply_plan(plan)
    assert (tree / "external").is_symlink()


def test_migration_rejects_reserved_domain_name(tmp_path):
    root = tmp_path / "data"
    (root / "md" / "system").mkdir(parents=True)

    plan = plan_migration(root)

    assert not plan.ok
    assert any("reserved" in conflict for conflict in plan.conflicts)
