import re
from pathlib import Path

from app.stores.db import SERIAL_TABLES, Database, is_postgres, translate


def test_translate_sqlite_sql_to_postgres():
    assert translate("INSERT INTO t (a, b) VALUES (?,?)") == "INSERT INTO t (a, b) VALUES (%s,%s)"
    assert "BIGSERIAL PRIMARY KEY" in translate("id INTEGER PRIMARY KEY AUTOINCREMENT, x TEXT")
    assert translate("SELECT * FROM t WHERE a LIKE '10%' AND b=?") == "SELECT * FROM t WHERE a LIKE '10%%' AND b=%s"


def test_database_url_kind():
    assert is_postgres("postgresql://u:p@h:5432/postgres") and is_postgres("postgres://x")
    assert not is_postgres("sqlite:///./app.db")


def test_sqlite_columns_helper():
    db = Database("sqlite:///:memory:")
    db.script("CREATE TABLE t (a INTEGER, b TEXT)")
    assert db.columns("t") == {"a", "b"}


def test_serial_tables_cover_every_identity_table_in_schema():
    """스키마에서 id 가 'generated always as identity' 인 테이블은 모두 SERIAL_TABLES 에 있어야 INSERT 뒤 id 를 받을 수 있다."""
    sql = (Path(__file__).resolve().parents[2] / "docs" / "db" / "fbgrowth_schema.sql").read_text(encoding="utf-8")
    # create table 이름 (...) 블록 안에 identity 가 있는 테이블 이름을 모은다
    identity = {m.group(1) for m in re.finditer(
        r"create table if not exists (\w+) \((?:(?!create table).)*?generated always as identity", sql, re.S | re.I)}
    assert identity and identity <= SERIAL_TABLES, identity - SERIAL_TABLES
