from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.factory import create_app
from app.services.grades import KST

ADMIN = {"Authorization": "Bearer admin-secret"}


def settings(**kw) -> Settings:
    base = dict(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None)
    return Settings(**{**base, **kw})


def login(c: TestClient, nickname: str, agree: bool = False) -> dict:
    """모의 카카오 로그인으로 회원을 만들고 JWT 헤더를 돌려준다. agree=True 면 광고성 문자 수신에 동의한다."""
    q = c.post("/api/auth/qr", json={"table_no": 1}).json()
    c.get(f"/api/auth/kakao/start?token={q['token']}")
    c.get("/api/auth/kakao/continue", params={"token": q["token"], **({"agree": "1"} if agree else {})},
          follow_redirects=False)
    c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": f"mock-{nickname}"})
    return {"Authorization": f"Bearer {c.get(f'/api/auth/qr/{q['secret']}').json()['access_token']}"}


def set_profile(c, headers, phone=None, birth_year=None, gender=None, consent=None):
    """카카오에서 받아 오는 값(휴대폰·출생연도·성별)과 로그인 때 받는 수신 동의를 테스트용으로 직접 채운다."""
    members = c.app.state.members
    mid = c.get("/api/members/me", headers=headers).json()["id"]
    for col, val in (("phone", phone), ("birth_year", birth_year), ("gender", gender)):
        if val is not None:
            members.db.run(f"UPDATE members SET {col}=? WHERE id=?", (val, mid))
    if consent is not None:
        members.set_marketing_consent(mid, consent)


@pytest.fixture
def client():
    with TestClient(create_app(settings())) as c:
        yield c


@pytest.fixture
def empty_menu_catalog(client):
    """테스트가 메뉴 전체 조건을 제어할 수 있도록 기본 시드 메뉴를 비운다."""
    shop = client.app.state.shop
    for menu in shop.menus():
        shop.delete_menu(menu["id"])


def at(hour: int, minute: int = 0):
    return lambda: datetime(2026, 10, 12, hour, minute, tzinfo=KST)
