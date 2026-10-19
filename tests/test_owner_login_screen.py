"""관리자 화면의 사장님 로그인(이메일/비밀번호): 서버가 Supabase 로그인을 지원할 때만 입력창이 나온다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

import admin_repository as ar
from app.core.settings import Settings
from app.factory import create_app
from shared import api

APP = str(ROOT / "admin" / "app.py")
OWNER_ID = "11111111-1111-4111-8111-111111111111"


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def make_server(supabase: bool):
    extra = dict(supabase_url="http://sb.test", supabase_anon_key="anon") if supabase else {}
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None, **extra)
    return TestClient(create_app(s))


@pytest.fixture
def owner_server(monkeypatch):
    """Supabase 가 켜진 서버. Supabase 로의 호출은 가짜 응답으로 대신하고, owner@x.com 만 사장님으로 등록한다."""
    def post(url, params=None, headers=None, json=None, timeout=None):
        ok = json["email"] == "owner@x.com" and json["password"] == "pw"
        return FakeResponse(200, {"access_token": "jwt-owner", "user": {"id": OWNER_ID, "email": json["email"]}}) if ok \
            else FakeResponse(400, {})

    def get(url, headers=None, timeout=None):
        return FakeResponse(200, {"id": OWNER_ID}) if headers["Authorization"] == "Bearer jwt-owner" else FakeResponse(401, {})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    with make_server(True) as c:
        c.app.state.owners.db.run("INSERT INTO owners (user_id) VALUES (?)", (OWNER_ID,))
        api.set_client(c)
        yield c
    api.set_client(None)


def test_owner_login_disabled_without_supabase():
    with make_server(False) as c:
        api.set_client(c)
        try:
            assert ar.owner_login_enabled() is False
        finally:
            api.set_client(None)


def test_connect_owner_logs_in_and_rejects_wrong_password(owner_server, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "api")
    assert ar.owner_login_enabled() is True
    bad = ar.connect_owner("owner@x.com", "wrong")
    assert bad.error and bad.repo is None
    good = ar.connect_owner("owner@x.com", "pw")
    assert good.error is None and good.token == "jwt-owner" and good.repo.source == "api"


def test_login_screen_shows_email_password_and_enters(owner_server, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "api")
    monkeypatch.setenv("ADMIN_SKIP_TOKEN", "0")  # 개발용 자동 입장을 꺼서 로그인 화면이 보이게 한다
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert [t.label for t in app.text_input] == ["이메일", "비밀번호"]
    app.text_input[0].set_value("owner@x.com")
    app.text_input[1].set_value("pw")
    app.button[0].click().run()
    assert app.session_state["owner"] is True and app.session_state["token"] == "jwt-owner" and not app.exception
