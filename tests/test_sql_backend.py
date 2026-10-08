from __future__ import annotations

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
