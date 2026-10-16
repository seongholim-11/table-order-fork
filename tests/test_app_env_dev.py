"""APP_ENV=dev 일 때만 손님·관리자 앱이 로그인 상태로 시작하는지 확인한다.

dev 가 아니면(prod·미설정) 어떤 경우에도 우회되면 안 된다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "user")]

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.core.settings import Settings
from app.factory import create_app
from shared import api

USER_APP = str(ROOT / "user" / "app.py")
ADMIN_APP = str(ROOT / "admin" / "app.py")


@pytest.fixture
def server():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None)
    with TestClient(create_app(s)) as c:
        api.set_client(c)
        yield c
    api.set_client(None)


def test_is_dev_only_when_exactly_dev(monkeypatch):
    for value, expected in [("dev", True), (" DEV ", True), ("prod", False), ("", False), ("development", False)]:
        monkeypatch.setenv("APP_ENV", value)
        assert api.is_dev() is expected


def test_is_dev_false_when_unset_and_no_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(api, "Path", lambda *_: tmp_path / "shared" / "api.py")  # backend/.env 가 없는 위치
    assert api.is_dev() is False


def test_user_app_auto_login_in_dev(server, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = AppTest.from_file(USER_APP, default_timeout=30).run()
    assert not app.exception
    assert app.session_state["member"]["nickname"].startswith("개발테스트")
    assert app.session_state["access_token"]
    # 로그인 팝업 없이 바로 룰렛이 돌아야 한다
    app.button(key="roulette_btn").click().run()
    assert not app.exception
    assert app.session_state["roulette"] is not None


def test_user_app_dev_login_even_without_server(monkeypatch):
    """서버가 안 닿아도(DB INSERT 불가) dev 에서는 임시 회원으로 로그인된 상태가 된다."""
    monkeypatch.setenv("APP_ENV", "dev")
    api.set_client(None)
    monkeypatch.setattr(api, "API_URL", "http://127.0.0.1:1")  # 아무도 듣지 않는 주소
    app = AppTest.from_file(USER_APP, default_timeout=30).run()
    assert not app.exception
    assert app.session_state["member"]["nickname"] == "개발테스트"
    app.button(key="roulette_btn").click().run()  # 서버 없이도 룰렛이 돌아야 한다
    assert app.session_state["roulette"] is not None
    api.set_client(None)


@pytest.mark.parametrize("env", ["prod", None])
def test_user_app_not_logged_in_when_not_dev(server, monkeypatch, env):
    if env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.setattr(api, "Path", lambda *_: Path("/nonexistent/shared/api.py"))  # backend/.env 도 없다고 가정
    else:
        monkeypatch.setenv("APP_ENV", env)
    app = AppTest.from_file(USER_APP, default_timeout=30).run()
    assert not app.exception
    assert app.session_state["member"] is None


@pytest.mark.parametrize("env", ["prod", "staging"])
def test_admin_app_asks_token_when_not_dev(monkeypatch, env):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.setenv("ADMIN_SKIP_TOKEN", "1")  # 켜 두어도 dev 가 아니면 무시된다
    app = AppTest.from_file(ADMIN_APP, default_timeout=30).run()
    assert len(app.text_input) == 1
    assert app.session_state["owner"] is False
