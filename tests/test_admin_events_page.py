"""관리자 '이벤트' 화면: 룰렛 칸·확률 가중치 편집이 서버(손님 화면이 읽는 콘텐츠)에 저장된다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin"), str(ROOT / "user")]

import pandas as pd
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
    assert first["종류"] == "할인" and first["할인율(%)"] == 5 and first["칸 문구"] == "모든 메뉴"
    assert t[t["종류"] == "서비스"]["서비스 메뉴"].notna().all()


def test_save_roulette_roundtrip_and_odds(repo):
    if isinstance(repo.backend, ar.ApiBackend):
        pytest.skip("GET 이 더미라 저장한 값이 조회에 반영되지 않음 - 해당 GET 을 DB 로 구현하면 이 skip 을 지운다")
    t = repo.roulette_table()
    t.loc[0, "확률 가중치"] = 3
    t.loc[1, "확률 가중치"] = 1
    t.loc[2:, "확률 가중치"] = 0
    repo.save_roulette(t)
    back = repo.roulette_table()
    assert list(back["확률 가중치"][:2]) == [3, 1] and repo.roulette_odds(back)[:2] == [75.0, 25.0]
    assert back.iloc[1]["서비스 메뉴"] == t.iloc[1]["서비스 메뉴"]
    new = pd.concat([back, pd.DataFrame([{"칸 문구": "<b>꽝</b>", "이모지": "😅", "종류": "할인", "할인율(%)": 10,
                                           "서비스 메뉴": None, "색상": "#112233", "확률 가중치": 1, "당첨 안내문": ""}])],
                    ignore_index=True)
    repo.save_roulette(new)
    last = repo.backend.roulette_prizes()[-1]
    assert last["label"] == "&lt;b&gt;꽝&lt;/b&gt;<br><b>10% 할인</b>" and last["short"] == "<b>꽝</b> 10% 할인" and last["weight"] == 1.0


@pytest.mark.parametrize("edit, msg", [
    (lambda t: t.drop(t.index[1:]), "2~8개"),
    (lambda t: t.assign(**{"확률 가중치": 0}), "하나는 있어야"),
    (lambda t: t.assign(색상="red"), "#RRGGBB"),
    (lambda t: t.assign(**{"칸 문구": " "}), "문구"),
    (lambda t: t.assign(**{"확률 가중치": -1}), "0 이상"),
    (lambda t: t.assign(**{"할인율(%)": 0}), "할인율"),
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
    assert app.button(key="roulette_save").disabled and app.button(key="roulette_undo").disabled  # 바뀐 게 없으면 비활성


def test_user_spin_follows_weights():
    prizes = [{"weight": 0}, {"weight": 5}, {"weight": 0}]
    assert {pick_prize_index(prizes) for _ in range(50)} == {1}
    assert {pick_prize_index([{}, {}, {}]) for _ in range(200)} == {0, 1, 2}  # weight 없으면 같은 확률(기존 동작)
    assert pick_prize_index([{"weight": 0}, {"weight": 0}]) in (0, 1)
