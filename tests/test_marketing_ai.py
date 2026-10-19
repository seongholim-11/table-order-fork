"""마케팅 화면의 대시보드/AI 탭 (더미 데이터, 키 없이 동작하는 규칙 기반 응답)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import copy

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
    assert any('class="rec recommendation-card"' in h.value for h in app.get("html"))


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
    assert app.sidebar.radio(key="nav_sub_마케팅").options == ["AI 챗봇", "AI 추천", "AI 문자", "F&B그로스 성과"]
    assert app.sidebar.radio(key="nav_sub_주문 이력").options == ["전체 주문", "고객별 주문"]
    assert [e.label for e in app.sidebar.expander] == ["📊 대시보드", "👥 고객 등급", "🧾 주문 이력", "💬 마케팅"]
    assert [e.proto.expanded for e in app.sidebar.expander] == [False, False, False, True]  # 선택된 묶음만 펼쳐서 시작
    assert "직원 호출" not in app.sidebar.radio(key="nav_top").options  # 직원 호출 메뉴는 제거됨
    app.sidebar.radio(key="nav_sub_주문 이력").set_value("고객별 주문").run()
    assert not app.exception and any("고객" in s.label for s in app.selectbox)
    assert app.query_params["page"] == "주문 이력" and app.query_params["tab"] == "고객별 주문"
    assert app.sidebar.radio(key="nav_sub_마케팅").value is None  # 다른 묶음의 선택은 풀린다
    app.sidebar.radio(key="nav_top").set_value("메뉴 관리").run()
    assert "tab" not in app.query_params and app.sidebar.radio(key="nav_sub_주문 이력").value is None


def test_rerecommend_cycles_through_recommendations():
    from admin.views.marketing import pick_recommendations
    recs = [{"title": str(i)} for i in range(7)]
    first, p1, pages = pick_recommendations(recs, 0)
    second, p2, _ = pick_recommendations(recs, 1)
    assert pages == 2 and (p1, p2) == (1, 2)
    assert [r["title"] for r in first] == ["0", "1", "2", "3"]
    assert [r["title"] for r in second] == ["4", "5", "6"]
    assert not ({r["title"] for r in first} & {r["title"] for r in second})
    assert pick_recommendations(recs, 2)[0] == first  # 끝까지 보면 처음으로
    assert pick_recommendations(recs[:2], 5)[2] == 1


def test_rerecommend_button_changes_cards():
    app = open_marketing("AI 추천")
    before = [h.value for h in app.get("html") if 'class="rec recommendation-card"' in h.value]
    app.button(key="mk_rerecommend").click().run()
    after = [h.value for h in app.get("html") if 'class="rec recommendation-card"' in h.value]
    assert not app.exception and before and after and before != after
    assert app.session_state["mk_rec_round"] == 1


def test_sms_recommendation_moves_to_sms_and_prefills_targets_and_body():
    app = open_marketing("AI 추천")
    execute = next(button for button in app.button if button.key and button.key.startswith("mk_execute_"))
    execute.click().run()
    assert not app.exception
    assert app.query_params["tab"] == "AI 문자"
    assert app.text_area(key="sms_body").value
    assert app.multiselect(key="sms_grades").value
    assert any("AI 문자 초안" in success.value for success in app.success)


def test_each_sms_button_is_rendered_with_its_own_numbered_card():
    """문자 추천에만 실행 버튼을 붙이고 기타 추천과 손님 응대 제안을 순서대로 표시한다."""
    app = open_marketing("AI 추천")
    recommendation_cards = [html.value for html in app.get("html")
                            if 'class="rec recommendation-card"' in html.value]
    execute_buttons = [button for button in app.button if button.key and button.key.startswith("mk_execute_")]
    groups = app.session_state["repo"].opportunities(0)["groups"]
    sms, guides = groups["sms"]["items"], groups["guide"]["items"]
    assert len(recommendation_cards) == len(sms) + len(guides)
    assert len(execute_buttons) == len(sms)
    assert all(button.help == f"{index}번 추천 실행: {card['title']}"
               for index, (button, card) in enumerate(zip(execute_buttons, sms), 1))
    html = " ".join(h.value for h in app.get("html"))
    assert html.index("1. AI 문자 추천") < html.index("2. 기타 AI 추천") < html.index("손님 응대 제안")
    for group in (sms, guides):
        assert all(any(f'<div class="rt">{index}. {card["title"]}</div>' in value
                       for value in recommendation_cards) for index, card in enumerate(group, 1))


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
    ids = members[members["전화번호 보유"] & members["마케팅 수신 동의"]
                  & ~members["수신거부"] & (members["등급"] == "휴면")]["customer_id"].tolist()
    assert full == len(ids) >= 2
    assert repo.sms_preview(["휴면"], "문구", member_ids=ids[1:])["targets"] == full - 1
    assert repo.sms_preview(["휴면"], "문구", member_ids=[])["ok"] is False


def test_ai_candidates_error_is_shown_instead_of_crashing():
    """서버가 시간 초과/오류로 답해도 버튼 콜백이 예외로 끝나 화면이 멈추면 안 된다."""
    from admin.views import marketing

    class BrokenRepo:
        source = "api"

        def sms_candidates(self):
            raise repo_mod.api.ApiUnavailable("timed out")

    marketing.ss["ai_candidates"] = ["old"]
    marketing.make_ai_candidates(BrokenRepo())
    assert marketing.ss["ai_candidates"] == [] and marketing.ss["ai_picked"] is None


class FakeChatServer:
    """서버 챗봇 API 흉내: 대화방을 메모리에 저장한다. (DummyBackend 를 서버 연결 상태로 속이는 데 쓴다)"""
    def __init__(self):
        self.sessions = {}

    def chat_create(self):
        sid = f"s{len(self.sessions) + 1}"
        self.sessions[sid] = {"id": sid, "title": "새 대화", "updated_at": f"2026-10-18T0{len(self.sessions)}:00:00+00:00",
                              "messages": [{"role": "assistant", "content": "인사"}]}
        return copy.deepcopy(self.sessions[sid])  # 실제 서버처럼 JSON 사본을 돌려준다(화면 상태와 같은 리스트를 공유하지 않게)

    def chat_sessions(self):
        return sorted(copy.deepcopy(list(self.sessions.values())), key=lambda s: s["updated_at"], reverse=True)

    def chat_get(self, sid):
        return copy.deepcopy(self.sessions[sid])

    def chat_send(self, sid, content):
        s = self.sessions[sid]
        new = [{"role": "user", "content": content}, {"role": "assistant", "content": f"답:{content}"}]
        s["messages"] += new
        s["title"] = content if s["title"] == "새 대화" else s["title"]
        return new


def test_server_chat_new_button_creates_room_and_list_switches(monkeypatch):
    import admin_dummy_data
    server = FakeChatServer()
    monkeypatch.setattr(admin_dummy_data.DummyBackend, "source", "api", raising=False)
    for name in ("chat_create", "chat_sessions", "chat_get", "chat_send"):
        monkeypatch.setattr(admin_dummy_data.DummyBackend, name, lambda self, *a, _n=name: getattr(server, _n)(*a),
                            raising=False)
    app = open_marketing()
    assert not app.exception
    assert len(server.sessions) == 1  # 처음 들어오면 대화방 1개가 만들어진다
    # 첫 질문을 하면 그 방 제목이 질문으로 바뀌고 목록에 보인다
    app.chat_input[0].set_value("저번주 매출").run()
    assert [m.markdown[0].value for m in app.chat_message] == ["인사", "저번주 매출", "답:저번주 매출"]
    # 새 대화 버튼: 새 대화방이 열리고(빈 화면) 목록에 추가된다
    new = next(b for b in app.button if b.key == "mk_chat_new")
    new.click().run()
    assert len(server.sessions) == 2
    assert [m.markdown[0].value for m in app.chat_message] == ["인사"]
    assert len(app.selectbox[0].options) == 2
    # 빈 새 대화에서 또 누르면 빈 방이 더 만들어지지 않는다
    next(b for b in app.button if b.key == "mk_chat_new").click().run()
    assert len(server.sessions) == 2
    # 목록에서 이전 대화를 고르면 그 대화가 열려 이어서 질문할 수 있다
    app.selectbox[0].select("s1").run()
    assert [m.markdown[0].value for m in app.chat_message] == ["인사", "저번주 매출", "답:저번주 매출"]
    app.chat_input[0].set_value("그 전주는?").run()
    assert server.sessions["s1"]["messages"][-1]["content"] == "답:그 전주는?"


def test_recommend_tab_shows_table_map_with_highlight():
    """AI 추천 화면의 손님 응대 제안에 테이블 배치도가 보이고, 제안이 있는 테이블만 눌러 볼 수 있다."""
    app = open_marketing("AI 추천")
    buttons = {b.key: b for b in app.button if b.key and b.key.startswith("mk_table_")}
    assert buttons, "테이블 배치도 버튼이 있어야 한다"
    enabled = [b for b in buttons.values() if not b.disabled]
    assert enabled and len(enabled) < len(buttons)  # 제안이 있는 테이블만 활성화
    enabled[0].click().run()
    assert not app.exception
