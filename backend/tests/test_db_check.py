from tests.conftest import ADMIN
from app.stores.db_check import EXPECTED_TABLES


def test_db_check_requires_admin(client):
    assert client.get("/admin/api/system/db").status_code == 401


def test_db_check_reports_sqlite_connection(client):
    """테스트는 SQLite 메모리 DB 라서 dialect 는 sqlite 이고, 연결 주소 같은 비밀은 응답에 없다."""
    r = client.get("/admin/api/system/db", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["dialect"] == "sqlite" and body["server_version"]
    assert body["tables"]["expected"] == len(EXPECTED_TABLES)
    assert body["tables"]["missing"] == []  # SQLite 는 없는 테이블을 따지지 않는다
    assert "database_url" not in r.text and "sqlite:///" not in r.text


def test_db_check_lists_legacy_tables(client):
    """옛 테이블이 남아 있으면 legacy_tables 로 알려 준다."""
    client.app.state.db.run("CREATE TABLE content (name TEXT)")
    assert client.get("/admin/api/system/db", headers=ADMIN).json()["legacy_tables"] == ["content"]


def test_db_check_reports_failure_without_500(client):
    """연결이 깨져도 500 대신 ok=false 와 오류 종류만 돌려준다."""
    client.app.state.db._conn.close()
    r = client.get("/admin/api/system/db", headers=ADMIN)
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["error"]
