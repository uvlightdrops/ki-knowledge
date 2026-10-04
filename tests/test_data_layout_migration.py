"""Tests for the v1 -> v2 data layout migration."""

import json
import sqlite3
from pathlib import Path

import pytest

from ki_knowledge.data_layout import MARKDOWN, PDF, DataLayout
from ki_knowledge.data_layout_migration import apply_plan, plan_v1_to_v2


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
        conn.execute("CREATE TABLE pdf_import_jobs (job_id TEXT, pdf_path TEXT)")
        conn.execute("INSERT INTO pdf_import_jobs VALUES ('1', ?)", (str(root / "pdf" / "Anthro" / "b.pdf"),))
        conn.execute("INSERT INTO pdf_import_jobs VALUES ('2', '/elsewhere/c.pdf')")
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
