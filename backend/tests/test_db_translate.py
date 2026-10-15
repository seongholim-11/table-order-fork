from app.stores.db import Database, is_postgres, translate


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
