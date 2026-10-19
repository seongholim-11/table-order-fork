from fastapi.testclient import TestClient

from app.factory import create_app
from tests.conftest import settings


def _make_test_client():
    """실제 .env의 PostgreSQL이 아니라 테스트용 SQLite로 앱을 띄운다."""
    return TestClient(create_app(settings()))


def test_health():
    with _make_test_client() as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_admin_requires_token():
    with _make_test_client() as client:
        assert client.get("/admin/api/orders").status_code == 401
