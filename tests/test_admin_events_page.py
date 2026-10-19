"""관리자 '이벤트' 화면: 룰렛 칸·확률 가중치 편집이 서버(손님 화면이 읽는 콘텐츠)에 저장된다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin"), str(ROOT / "user")]

import pytest
from streamlit.testing.v1 import AppTest

import admin_repository as ar
from admin_dummy_data import DummyBackend
from test_admin_menu_page import APP, server  # noqa: F401 - server 픽스처 재사용
from user.state.roulette import pick_prize_index


def repo_for(kind, server):  # noqa: F811
    return ar.AdminRepository(DummyBackend() if kind == "dummy" else ar.ApiBackend("admin-secret"))


@pytest.fixture(params=["dummy", "api"])
def repo(request, server):  # noqa: F811
    return repo_for(request.param, server)


def test_roulette_table_matches_prizes(repo):
    t = repo.roulette_table()
    assert list(t.columns) == ar.ROULETTE_COLUMNS and len(t) >= 3
    first = t.iloc[0]
    assert first["종류"] == "할인" and first["할인율(%)"] == 5
    assert t[t["종류"] == "서비스"]["서비스 메뉴"].notna().all()
    choices = repo.roulette_menu_choices()
    assert choices and all(choice["label"].startswith("[") for choice in choices)
    # 전체 메뉴 할인과 안주·음료 서비스 항목만 룰렛 선택지로 제공한다.
    assert {choice["id"] for choice in choices} == {None, "a1", "a4", "a11", "d7", "d8", "d1", "j1", "b1"}
    assert next(choice for choice in choices if choice["id"] == "a4")["emoji"] == "🥚"


def test_save_roulette_roundtrip_and_odds(repo):
    t = repo.roulette_table()
    # 10의 배수가 아닌 직접 입력값도 합계가 100이면 그대로 저장된다.
    t["확률 가중치"] = [37, 23, 17, 13, 9, 1]
    repo.save_roulette(t)
    back = repo.roulette_table()
    assert list(back["확률 가중치"]) == [37, 23, 17, 13, 9, 1]
    assert repo.roulette_odds(back) == [37.0, 23.0, 17.0, 13.0, 9.0, 1.0]
    assert back.iloc[1]["서비스 메뉴"] == t.iloc[1]["서비스 메뉴"]
    back.loc[0, "할인율(%)"] = 10
    repo.save_roulette(back)
    first = repo.backend.roulette_prizes()[0]
    assert first["label"] == "모든 메뉴<br><b>10% 할인</b>" and first["short"] == "전 메뉴 10% 할인" and first["weight"] == 37.0
    assert repo.backend.roulette_prizes()[1]["emoji"] == "🐟"  # 맛보기 먹태구이에 맞춰 자동 배정


@pytest.mark.parametrize("edit, msg", [
    (lambda t: t.drop(t.index[1:]), "2~8개"),
    (lambda t: t.assign(**{"확률 가중치": 0}), "합계를 100%"),
    (lambda t: t.assign(**{"확률 가중치": 17}), "합계를 100%"),
    (lambda t: t.assign(**{"확률 가중치": 0.5}), "1% 단위"),
    (lambda t: t.assign(색상="red"), "#RRGGBB"),
    (lambda t: t.assign(**{"확률 가중치": -1}), "0 이상"),
    (lambda t: t.assign(**{"할인율(%)": 0}), "할인율"),
    (lambda t: t.assign(종류="서비스", **{"서비스 메뉴": None}), "서비스 메뉴"),
])
def test_save_roulette_rejects_bad_input(repo, edit, msg):
    t = repo.roulette_table()
    t.loc[t["종류"] == "서비스", "서비스 메뉴"] = t[t["종류"] == "서비스"]["서비스 메뉴"]
    with pytest.raises(ar.CategoryError, match=msg):
        repo.save_roulette(edit(t))


def test_page_shows_event_and_preview(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    app.sidebar.radio(key="nav_top").set_value("이벤트").run()
    assert not app.exception
    assert any("행운의 룰렛" in h.value for h in app.get("html"))
    assert any("conic-gradient" in h.value and "%" in h.value for h in app.get("html"))
    menu_picker = next(selectbox for selectbox in app.selectbox
                       if selectbox.key and selectbox.key.startswith("roulette_menu_"))
    assert {option.split("] ")[-1] for option in menu_picker.options} == {
        "전체 메뉴", "맛보기 먹태구이", "계란말이", "노가리 구이", "라면", "짜장라면",
        "탄산음료", "소주 1병", "생맥주 1잔"}
    weight_input = app.number_input(key="roulette_weight_0-0")
    assert weight_input.label == "확률 (%)" and weight_input.min == 0 and weight_input.max == 100
    assert app.button(key="roulette_save").label == "저장하기"
    assert not [button for button in app.button if button.label in ("변경 저장", "↩ 되돌리기")]

    # 합계가 틀린 상태에서는 저장되지 않고, 100%로 맞추면 입력값이 유지된다.
    saved = app.session_state["repo"].backend.roulette_prizes()
    app.number_input(key="roulette_weight_0-0").set_value(37).run()
    app.button(key="roulette_save").click().run()
    assert not app.exception and app.error
    assert any("합계를 100%" in error.value for error in app.error)
    assert app.session_state["repo"].backend.roulette_prizes() == saved
    app.number_input(key="roulette_weight_0-1").set_value(23).run()
    assert any("확률 합계 100%" in success.value for success in app.success)
    app.button(key="roulette_save").click().run()
    assert not app.exception and not app.error
    assert app.number_input(key="roulette_weight_1-0").value == 37
    assert app.number_input(key="roulette_weight_1-1").value == 23


def test_all_menu_switches_service_to_discount_and_saves(monkeypatch):
    # 이미 서비스로 렌더링된 칸에서 전체 메뉴를 골라도 이전 위젯 값이 남지 않아야 한다.
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    app.sidebar.radio(key="nav_top").set_value("이벤트").run()
    assert not app.exception
    assert app.selectbox(key="roulette_kind_0-1").value == "서비스"
    app.selectbox(key="roulette_menu_0-1").select(ar.ALL_MENU_LABEL).run()
    assert not app.exception
    kind = app.selectbox(key="roulette_kind_0-1")
    assert kind.value == "할인" and kind.disabled
    rate = app.selectbox(key="roulette_rate_0-1")
    assert not rate.disabled
    rate.select(10).run()
    assert any("10% 할인" in h.value for h in app.get("html"))
    app.button(key="roulette_save").click().run()
    assert not app.exception and not app.error
    saved = app.session_state["repo"].backend.roulette_prizes()[1]
    assert saved["kind"] == "discount" and saved["percent"] == 10


def test_user_spin_follows_weights():
    prizes = [{"weight": 0}, {"weight": 5}, {"weight": 0}]
    assert {pick_prize_index(prizes) for _ in range(50)} == {1}
    assert {pick_prize_index([{}, {}, {}]) for _ in range(200)} == {0, 1, 2}  # weight 없으면 같은 확률(기존 동작)
    assert pick_prize_index([{"weight": 0}, {"weight": 0}]) in (0, 1)
