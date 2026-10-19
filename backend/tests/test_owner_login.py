"""사장님 로그인(Supabase Auth 이메일/비밀번호)과 관리자 인증을 확인한다. Supabase 호출은 가짜 응답으로 대신한다."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from tests.conftest import ADMIN, settings

OWNER_ID = "11111111-1111-4111-8111-111111111111"
STRANGER_ID = "22222222-2222-4222-8222-222222222222"
SB = dict(supabase_url="http://sb.test", supabase_anon_key="anon")


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


@pytest.fixture
def fake_supabase(monkeypatch):
    """비밀번호 로그인과 사용자 조회를 흉내 낸다. 이메일이 owner@/stranger@ 이고 비밀번호가 pw 이면 로그인된다."""
    users = {"owner@x.com": OWNER_ID, "stranger@x.com": STRANGER_ID}

    def post(url, params=None, headers=None, json=None, timeout=None):
        user_id = users.get(json["email"])
        if user_id and json["password"] == "pw":
            return FakeResponse(200, {"access_token": f"jwt-{user_id}", "user": {"id": user_id, "email": json["email"]}})
        return FakeResponse(400, {})

    def get(url, headers=None, timeout=None):
        token = headers["Authorization"].removeprefix("Bearer ")
        return FakeResponse(200, {"id": token.removeprefix("jwt-")}) if token.startswith("jwt-") else FakeResponse(401, {})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)


def make_client(**kw):
    c = TestClient(create_app(settings(**SB, **kw)))
    c.app.state.owners.db.run("INSERT INTO owners (user_id) VALUES (?)", (OWNER_ID,))
    return c


def test_config_tells_screen_whether_owner_login_exists(client):
    assert client.get("/api/auth/owner/config").json() == {"enabled": False}  # Supabase 설정이 없으면 토큰 화면
    assert make_client().get("/api/auth/owner/config").json() == {"enabled": True}


def test_owner_login_only_for_registered_owner(fake_supabase):
    with make_client() as c:
        ok = c.post("/api/auth/owner/login", json={"email": "owner@x.com", "password": "pw"})
        assert ok.status_code == 200 and ok.json()["access_token"] == f"jwt-{OWNER_ID}"
        assert c.post("/api/auth/owner/login", json={"email": "owner@x.com", "password": "bad"}).status_code == 401
        # Supabase 계정은 있지만 owners 에 없는 사람은 들어올 수 없다
        assert c.post("/api/auth/owner/login", json={"email": "stranger@x.com", "password": "pw"}).status_code == 403


def test_owner_login_needs_supabase_settings(client):
    assert client.post("/api/auth/owner/login", json={"email": "a@b.c", "password": "pw"}).status_code == 503


def test_admin_api_accepts_owner_token_not_stranger(fake_supabase):
    with make_client() as c:
        assert c.get("/admin/api/menus", headers={"Authorization": f"Bearer jwt-{OWNER_ID}"}).status_code == 200
        assert c.get("/admin/api/menus", headers={"Authorization": f"Bearer jwt-{STRANGER_ID}"}).status_code == 401
        assert c.get("/admin/api/menus", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert c.get("/admin/api/menus", headers=ADMIN).status_code == 200  # 개발용 토큰은 dev 에서 계속 허용


def test_prod_with_supabase_rejects_admin_token(fake_supabase):
    with make_client(app_env="prod", jwt_secret="x" * 32, admin_token="not-default") as c:
        assert c.get("/admin/api/menus", headers={"Authorization": "Bearer not-default"}).status_code == 401
        assert c.get("/admin/api/menus", headers={"Authorization": f"Bearer jwt-{OWNER_ID}"}).status_code == 200


def test_chat_rooms_belong_to_logged_in_owner(fake_supabase):
    with make_client() as c:  # CHAT_OWNER_ID 설정 없이도 로그인한 사장님의 대화방이 만들어진다
        h = {"Authorization": f"Bearer jwt-{OWNER_ID}"}
        created = c.post("/admin/api/marketing/chat/sessions", headers=h)
        assert created.status_code == 201
        assert [s["id"] for s in c.get("/admin/api/marketing/chat/sessions", headers=h).json()] == [created.json()["id"]]
        assert c.post("/admin/api/marketing/chat/sessions", headers=ADMIN).status_code == 503  # 토큰 입장은 CHAT_OWNER_ID 필요
