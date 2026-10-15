"""마케팅 화면의 대시보드/AI 탭 (더미 데이터, 키 없이 동작하는 규칙 기반 응답)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import pytest
from streamlit.testing.v1 import AppTest

import admin_repository as repo_mod
import marketing_ai

APP = str(ROOT / "admin" / "app.py")


@pytest.fixture(autouse=True)
def dummy_mode(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")


def open_marketing(tab=None):
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["page"] = "마케팅"
    if tab:
        app.query_params["tab"] = tab
    app.run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_ai_context_and_recommendations():
    repo = repo_mod.connect("change-me").repo
    ctx = marketing_ai.build_context(repo, repo_mod.DEFAULT_RULE)
    assert ctx["members"]["total"] > 0 and ctx["orders"]["count"] > 0
    recs = marketing_ai.recommend(ctx)
    assert recs and all({"title", "why", "action"} <= r.keys() for r in recs)
    answer = marketing_ai.get_client().reply("인기 메뉴가 뭐야?", ctx)
    assert "가장 많이 팔린 메뉴" in answer


def test_default_tab_is_chatbot_and_other_tabs_render_separately():
    app = open_marketing()
    assert not app.exception
    assert app.query_params["tab"] == "AI 챗봇"
    assert app.chat_input and not app.text_area
    app.chat_input[0].set_value("휴면 고객 어떻게 되찾을까?").run()
    assert not app.exception
    texts = [m.markdown[0].value if m.markdown else "" for m in app.chat_message]
    assert len(texts) == 3 and "휴면" in texts[-1]


def test_recommend_tab_has_only_recommendations():
    app = open_marketing("AI 추천")
    assert not app.exception
    assert not app.chat_input and not app.text_area
    assert any('class="recs"' in h.value for h in app.get("html"))


def test_sms_tab_has_the_message_editor():
    app = open_marketing("AI 문자")
    assert not app.exception
    assert app.text_area and not app.chat_input


def test_switching_tab_updates_url():
    app = open_marketing()
    app.sidebar.radio(key="nav_sub_마케팅").set_value("AI 문자").run()
    assert app.query_params["tab"] == "AI 문자" and app.query_params["page"] == "마케팅"
    assert app.text_area


def test_sidebar_sub_menus_are_collapsible_and_select_tabs():
    app = open_marketing("AI 추천")
    assert app.sidebar.radio(key="nav_sub_마케팅").options == ["AI 챗봇", "AI 추천", "AI 문자"]
    assert app.sidebar.radio(key="nav_sub_주문 이력").options == ["전체 주문", "고객별 주문"]
    assert [e.label for e in app.sidebar.expander] == ["🧾 주문 이력", "💬 마케팅"]
    assert [e.proto.expanded for e in app.sidebar.expander] == [False, True]  # 선택된 묶음만 펼쳐서 시작
    assert "직원 호출" not in app.sidebar.radio(key="nav_top").options
    app.sidebar.radio(key="nav_sub_주문 이력").set_value("고객별 주문").run()
    assert not app.exception and any("고객" in s.label for s in app.selectbox)
    assert app.query_params["page"] == "주문 이력" and app.query_params["tab"] == "고객별 주문"
    assert app.sidebar.radio(key="nav_sub_마케팅").value is None  # 다른 묶음의 선택은 풀린다
    app.sidebar.radio(key="nav_top").set_value("대시보드").run()
    assert "tab" not in app.query_params and app.sidebar.radio(key="nav_sub_주문 이력").value is None


def test_rerecommend_cycles_through_recommendations():
    from admin.views.marketing import pick_recommendations
    recs = [{"title": str(i)} for i in range(7)]
    first, p1, pages = pick_recommendations(recs, 0)
    second, p2, _ = pick_recommendations(recs, 1)
    assert pages == 2 and (p1, p2) == (1, 2)
    assert [r["title"] for r in first] == ["0", "1", "2", "3"]
    assert [r["title"] for r in second] == ["4", "5", "6", "0"]
    assert pick_recommendations(recs, 2)[0] == first  # 끝까지 보면 처음으로
    assert pick_recommendations(recs[:2], 5)[2] == 1


def test_rerecommend_button_changes_cards():
    app = open_marketing("AI 추천")
    before = [h.value for h in app.get("html") if 'class="recs"' in h.value]
    app.button(key="mk_rerecommend").click().run()
    after = [h.value for h in app.get("html") if 'class="recs"' in h.value]
    assert not app.exception and before and after and before != after
    assert app.session_state["mk_rec_round"] == 1


def test_keyword_recipients_and_combos():
    assert marketing_ai.keyword_grades(["휴면"]) == ["휴면"]
    assert marketing_ai.keyword_grades(["주문", "단골"]) == ["단골"]
    assert marketing_ai.keyword_grades(["휴면", "단골"]) == []  # 교집합이 비면 빈 목록
    combos = marketing_ai.keyword_combos()
    assert ("휴면", "단골") not in combos and ("주문", "단골") in combos
    assert all(marketing_ai.keyword_grades(c) for c in combos)


def test_generate_sms_falls_back_to_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    repo = repo_mod.connect("change-me").repo
    ctx = marketing_ai.build_context(repo, repo_mod.DEFAULT_RULE)
    text, source = marketing_ai.generate_sms(["날씨", "행사"], ctx, weather="비 오는 날", event="치맥 데이")
    assert source == "template" and "비 오는 날" in text and "치맥 데이" in text


def test_generate_sms_uses_ai_and_survives_failure(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    ctx = marketing_ai.build_context(repo_mod.connect("change-me").repo, repo_mod.DEFAULT_RULE)
    monkeypatch.setattr(marketing_ai, "_ask_claude", lambda *a: "AI 문구")
    assert marketing_ai.generate_sms(["주문"], ctx) == ("AI 문구", "ai")

    def boom(*a):
        raise marketing_ai.httpx.ConnectError("x")
    monkeypatch.setattr(marketing_ai, "_ask_claude", boom)
    assert marketing_ai.generate_sms(["주문"], ctx)[1] == "template"


def test_suggest_candidates_gives_up_to_five_with_recipients(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ctx = marketing_ai.build_context(repo_mod.connect("change-me").repo, repo_mod.DEFAULT_RULE)
    cands = marketing_ai.suggest_candidates(ctx)
    assert 4 <= len(cands) <= 5
    assert all(c["grades"] and c["body"] and c["source"] == "template" for c in cands)


def test_ai_button_shows_candidates_and_editable_recipients(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = open_marketing("AI 문자")
    assert not [b for b in app.button if b.label.startswith("🆕") or b.label.startswith("💤 휴면 복귀")]  # 빠른 문구 제거
    app.button(key="ai_sms_generate").click().run()
    assert not app.exception
    assert 4 <= len([b for b in app.button if b.key and b.key.startswith("ai_cand_")]) <= 5
    app.button(key="ai_cand_1").click().run()  # 두 번째 후보: 수신자·본문이 채워진다
    cand = app.session_state["ai_candidates"][1]
    assert app.multiselect(key="sms_grades").value == cand["grades"]
    assert app.text_area(key="sms_body").value == cand["body"]
    ids = [int(i) for i in app.session_state["repo"].members(app.session_state["grade_rule"]).query(
        "`마케팅 수신 동의` and not 수신거부 and 등급 in @cand['grades']")["customer_id"]]
    assert ids  # 수신자 목록이 비어 있지 않다


def test_removing_a_recipient_shrinks_send_target(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    repo = repo_mod.connect("change-me").repo
    full = repo.sms_preview(["휴면"], "문구")["targets"]
    members = repo.members(repo_mod.DEFAULT_RULE)
    ids = members[members["마케팅 수신 동의"] & ~members["수신거부"] & (members["등급"] == "휴면")]["customer_id"].tolist()
    assert full == len(ids) >= 2
    assert repo.sms_preview(["휴면"], "문구", member_ids=ids[1:])["targets"] == full - 1
    assert repo.sms_preview(["휴면"], "문구", member_ids=[])["ok"] is False
