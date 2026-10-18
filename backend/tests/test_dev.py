from fastapi.testclient import TestClient

from app.factory import create_app
from tests.conftest import settings


def test_dev_db_test_is_hidden_by_default(client):
    assert client.post("/api/dev/db-test").status_code == 404


def test_dev_db_test_writes_and_reads_test_table():
    app = create_app(settings(dev_test_button=True))
    app.state.db.script("""
        CREATE TABLE test (
            id TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with TestClient(app) as c:
        response = c.post("/api/dev/db-test")

    assert response.status_code == 200
    assert response.json() == {"result": 1}
    assert app.state.db.one("SELECT COUNT(*) AS count FROM test")["count"] == 1
