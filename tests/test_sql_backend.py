from __future__ import annotations

from unittest.mock import MagicMock

from ki_knowledge.integrations.sql_backend import StoreTarget, connect, ilike_operator, json_text, translate_sql


def test_translate_placeholders_named_and_percent():
    sql = translate_sql("SELECT ? AS a, :name AS b, '100%' AS pct, ?::vector AS v", "postgres")
    assert "%s AS a" in sql
    assert "%(name)s AS b" in sql
    assert "'100%%'" in sql
    assert "%s::vector" in sql


def test_sqlite_row_mapping_and_helpers(tmp_path):
    target = StoreTarget.sqlite(tmp_path / "db.sqlite")
    with connect(target) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, metadata_json TEXT, name TEXT)")
        conn.execute("INSERT INTO t (metadata_json, name) VALUES (?, ?)", ('{"source_id":"S1"}', "Alpha"))
        row = conn.execute(f"SELECT id, name, {json_text('metadata_json', 'source_id', conn.dialect)} AS source_id FROM t WHERE name {ilike_operator(conn.dialect)} ?", ("alpha",)).fetchone()
    assert row[0] == 1
    assert row["name"] == "Alpha"
    assert dict(row)["source_id"] == "S1"


def test_postgres_read_only_connection_does_not_create_schema(monkeypatch):
    from ki_knowledge.integrations import sql_backend

    driver = MagicMock()
    monkeypatch.setattr(sql_backend, "psycopg", driver)
    raw = driver.connect.return_value
    cursor = raw.cursor.return_value.__enter__.return_value
    with connect(StoreTarget.postgres("postgresql://unused/db", "knowledge"), read_only=True):
        pass
    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        "SET TRANSACTION READ ONLY", 'SET search_path TO "knowledge", public',
    ]
    raw.commit.assert_called_once()
    raw.close.assert_called_once()


def test_read_only_sqlite_uri_preserves_special_path_characters(tmp_path):
    target = StoreTarget.sqlite(tmp_path / "blocks ?#%.sqlite")
    with connect(target) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES (?)", ("stored",))
    with connect(target, read_only=True) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "stored"
