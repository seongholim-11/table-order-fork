from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.factory import create_app


def make_client(enabled: bool) -> TestClient:
    config = Settings(database_url="sqlite:///:memory:", jwt_secret="x" * 32,
                      admin_token="admin-secret", dev_test_button=enabled, _env_file=None)
    app = create_app(config)
    # 운영 스키마는 별도 SQL로 만들며, 자동 테스트에서는 같은 모양의 임시 테이블만 준비한다.
    app.state.db.script("CREATE TABLE test (id TEXT PRIMARY KEY, value TEXT NOT NULL, created_at TEXT)")
    return TestClient(app)


def test_db_test_is_hidden_when_disabled():
    with make_client(False) as client:
        assert client.post("/api/dev/db-test").status_code == 404


def test_db_test_writes_and_reads_same_row():
    with make_client(True) as client:
        assert client.post("/api/dev/db-test").json() == {"result": 1}
        rows = client.app.state.db.all("SELECT id, value FROM test")
        assert len(rows) == 1
        assert rows[0]["id"] and rows[0]["value"]
