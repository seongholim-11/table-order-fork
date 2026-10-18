"""수용 1-2: 새 API부터 고객 화면까지 연결하고 더미 모드도 유지한다."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import admin_repository as repo_mod
from admin_dummy_data import DummyBackend
from app.core.settings import Settings
from app.factory import create_app
from shared import api


@pytest.fixture
def server():
    # 실제 DB·문자를 건드리지 않는 메모리 서버만 화면에 연결한다.
    config = Settings(database_url="sqlite:///:memory:", app_env="dev", jwt_secret="x" * 32,
                      admin_token="admin-secret", grade_regular_visits=8, _env_file=None)
    with TestClient(create_app(config)) as client:
        member = client.app.state.members.upsert_login("grade-screen", "방문 7회 회원")
        client.app.state.db.run("UPDATE members SET visit_count=7 WHERE id=?", (member["id"],))
        api.set_client(client)
        try:
            yield client
        finally:
            api.set_client(None)


def open_rules(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "api")
    app = AppTest.from_file(str(ROOT / "admin/app.py"), default_timeout=30).run()
    app.text_input[0].set_value("admin-secret")
    app.button[0].click().run()
    app.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    assert not app.exception
    return app


def test_repository_matches_server_summary_and_keeps_dummy_contract(server):
    real = repo_mod.AdminRepository(repo_mod.ApiBackend("admin-secret"))
    counts = real.customer_grades()
    assert counts == {"신규": 0, "재방문": 1, "단골": 0, "휴면": 0, "dormant_count": 0}
    assert real.customer_grade_rules()["regular"] == 8
    dummy = repo_mod.AdminRepository(DummyBackend())
    assert dummy.customer_grades().keys() == counts.keys()
    rule = dummy.customer_grade_rules()
    members = dummy.members(rule)
    for grade in repo_mod.GRADES:
        assert dummy.customer_grades(rule)[grade] == int((members["등급"] == grade).sum())


def test_customer_screen_keeps_conditions_until_save_and_does_not_write_on_edit(server, monkeypatch):
    app = open_rules(monkeypatch)
    assert app.number_input(key="rule_regular").value == 8
    app.number_input(key="rule_regular").set_value(5).run()
    assert not app.exception
    assert app.session_state["repo"].customer_grades(app.session_state["grade_rule"])["단골"] == 0
    assert app.session_state["repo"].customer_grade_rules()["regular"] == 8
    app.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert not app.exception
    assert app.dataframe[0].value.iloc[0]["등급"] == "재방문"
    app.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    assert app.number_input(key="rule_regular").value == 8
    # 입력만으로 조건을 바꾸지 않고, 복원 버튼을 누를 때 초기 기준으로 바뀐다.
    app.number_input(key="rule_regular").set_value(6).run()
    app.button(key="rule_reset").click().run()
    assert not app.exception
    assert app.number_input(key="rule_regular").value == 5
    assert app.session_state["grade_rule_preview"]["regular"] == 5
    assert app.session_state["grade_rule"]["regular"] == 8
    assert app.session_state["repo"].customer_grade_rules()["regular"] == 8


def test_summary_cards_use_new_endpoint_and_handle_empty_database(server, monkeypatch):
    # 회원이 없어도 카드에는 0명이 표시되고 빈 목록 화면이 오류 없이 열려야 한다.
    original = server.app.state.members.all
    monkeypatch.setattr(server.app.state.members, "all", lambda: [])
    app = open_rules(monkeypatch)
    assert not app.exception
    app.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert not app.exception and app.dataframe[0].value.empty
    counts = app.session_state["repo"].customer_grades(app.session_state["grade_rule"])
    assert all(value == 0 for value in counts.values())
    monkeypatch.setattr(server.app.state.members, "all", original)
