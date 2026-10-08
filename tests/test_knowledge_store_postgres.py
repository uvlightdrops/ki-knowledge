from __future__ import annotations

import os
import uuid

import pytest

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.integrations.sql_backend import StoreTarget, connect
from ki_knowledge.knowledge.models import KnowledgeSource, KnowledgeBlockRecord


def _exercise(target):
    store = KnowledgeStore(target)
    store.upsert_source(KnowledgeSource(source_id="s1", source_type="test", title="Source", location="/x", metadata={"kind":"demo"}))
    store.upsert_record(KnowledgeBlockRecord(block_id="b1", source_id="s1", block_type="note", title="Hello", content="Hello World", parent_block_id=None, path="/", order_index=1, tags=["T"], metadata={}))
    store.add_embedding("b1", "m", [1.0, 2.5])
    assert store.get_record("b1").title == "Hello"
    assert store.browse_records("s1", query_text="hello")[1] == 1
    assert store.get_embedding("b1") == [1.0, 2.5]

    sem = SemanticTermStore(target if isinstance(target, StoreTarget) and target.is_postgres else target.sqlite_path.parent / "sem.sqlite")
    term_id = sem.upsert_term("OAuth2 Service")
    sem.store_domain_candidates([])
    sem.enqueue_jobs(limit=10)
    assert sem.get_term(term_id).canonical_label == "OAuth2 Service"


def test_store_sqlite(tmp_path):
    _exercise(StoreTarget.sqlite(tmp_path / "knowledge.sqlite"))


@pytest.mark.skipif(not os.getenv("KI_TEST_POSTGRES_DSN"), reason="KI_TEST_POSTGRES_DSN unset")
def test_store_postgres():
    schema = f"test_knowledge_{uuid.uuid4().hex[:12]}"
    target = StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema=schema)
    try:
        _exercise(target)
    finally:
        with connect(StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema="public")) as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

@pytest.mark.skipif(not os.getenv("KI_TEST_POSTGRES_DSN"), reason="KI_TEST_POSTGRES_DSN unset")
def test_migration_command_copies_small_fixture(tmp_path, monkeypatch):
    from django.conf import settings
    from django.core.management import call_command

    src = tmp_path / "knowledge.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(src))
    monkeypatch.setenv("KNOWLEDGE_DATA_ROOT", str(tmp_path))
    source_store = KnowledgeStore(StoreTarget.sqlite(src))
    source_store.upsert_source(KnowledgeSource(source_id="s1", source_type="test", title="Source", location="/x", metadata={"ok": True}))
    source_store.upsert_record(KnowledgeBlockRecord(block_id="b1", source_id="s1", block_type="note", title="Hello", content="Hello", parent_block_id=None, path="/", order_index=1, tags=[], metadata={}))
    source_store.add_embedding("b1", "m", [0.1, 0.2])

    schema = f"test_migrate_{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(settings, "KNOWLEDGE_STORE_TARGET", StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema=schema), raising=False)
    try:
        call_command(
            "migrate_knowledge_store_to_postgres",
            "--apply",
            "--confirm-services-stopped",
            "--replace",
            "--knowledge-schema",
            schema,
            "--knowledge-only",
            verbosity=0,
        )
        with connect(StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema=schema)) as conn:
            assert conn.execute("SELECT COUNT(*) FROM knowledge_blocks").fetchone()[0] == 1
            assert conn.execute("SELECT vector_json::text FROM knowledge_embeddings WHERE block_id=?", ("b1",)).fetchone()[0] == "[0.1,0.2]"
    finally:
        with connect(StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema="public")) as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
