"""AI 챗봇(/admin/api/marketing/chat/sessions…) 테스트. 제미나이 호출은 가짜로 바꿔 끼운다."""

import httpx
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import chat as chat_service
from tests.conftest import ADMIN, settings

BASE = "/admin/api/marketing/chat/sessions"
OWNER = "11111111-1111-1111-1111-111111111111"


def make(**kw):
    return TestClient(create_app(settings(chat_owner_id=OWNER, **kw)))


def fake_gemini(monkeypatch, reply="지난주 매출은 0원이에요.", fail=None):
    """제미나이 대신 정해 둔 답을 돌려주고, 받은 시스템 프롬프트·대화를 기록한다."""
    seen = {}

    def ask(self, system, history, question):
        seen.update(system=system, history=history, question=question)
        if fail:
            raise fail
        return reply
    monkeypatch.setattr(chat_service.ChatService, "_ask_gemini", ask)
    return seen


def test_create_session_has_greeting_and_lists_recent_first():
    with make() as c:
        a = c.post(BASE, headers=ADMIN)
        assert a.status_code == 201
        assert [m["role"] for m in a.json()["messages"]] == ["assistant"]
        b = c.post(BASE, headers=ADMIN).json()
        ids = [s["id"] for s in c.get(BASE, headers=ADMIN).json()]
        assert ids == [b["id"], a.json()["id"]]  # 최근에 만든 대화가 먼저


def test_question_saves_user_and_assistant_messages(monkeypatch):
    seen = fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "저번주 총 매출 알려줘"})
        assert r.status_code == 201
        assert [m["role"] for m in r.json()["messages"]] == ["user", "assistant"]
        session = c.get(f"{BASE}/{sid}", headers=ADMIN).json()
        assert [m["role"] for m in session["messages"]] == ["assistant", "user", "assistant"]
        assert session["title"] == "저번주 총 매출 알려줘"  # 첫 질문이 제목
    assert "저번 주" in seen["system"] and "[매장 데이터]" in seen["system"]
    assert seen["question"] == "저번주 총 매출 알려줘"


def test_summary_sums_last_week_by_server(monkeypatch):
    """제미나이가 아니라 서버가 지난주 합계를 계산해 프롬프트에 넣는다."""
    seen = fake_gemini(monkeypatch)
    # 오늘 기준 지난주 월요일 낮(KST)에 3만원 + 2만원 주문을 직접 넣는다
    from datetime import datetime, timedelta
    from app.services.grades import KST
    today = datetime.now(KST).date()
    monday = today - timedelta(days=today.weekday() + 7)
    stamp = datetime(monday.year, monday.month, monday.day, 12, tzinfo=KST).isoformat()
    with make(gemini_api_key="k") as c:
        db = c.app.state.db
        for total in (30000, 20000):
            db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?,?,?)", (1, total, stamp))
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "저번주 매출?"})
    assert "매출 50,000원, 주문 2건" in seen["system"]


def test_history_is_sent_without_leading_greeting(monkeypatch):
    seen = fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "첫 질문"})
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "둘째 질문"})
    assert [m["content"] for m in seen["history"] if m["role"] == "user"] == ["첫 질문"]


def test_no_api_key_answers_with_guide_not_500():
    with make(gemini_api_key="") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 201
        assert "GEMINI_API_KEY" in r.json()["messages"][1]["content"]


def test_gemini_failure_returns_error_and_saves_nothing(monkeypatch):
    fake_gemini(monkeypatch, fail=httpx.ConnectError("down"))
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 502
        assert len(c.get(f"{BASE}/{sid}", headers=ADMIN).json()["messages"]) == 1  # 인사 메시지뿐


def test_rate_limit_message(monkeypatch):
    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))
    fake_gemini(monkeypatch, fail=httpx.HTTPStatusError("limit", request=resp.request, response=resp))
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 502 and "한도" in r.json()["detail"]


def test_delete_removes_messages_and_missing_is_404(monkeypatch):
    fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "질문"})
        assert c.delete(f"{BASE}/{sid}", headers=ADMIN).status_code == 204
        assert c.get(f"{BASE}/{sid}", headers=ADMIN).status_code == 404
        assert c.app.state.db.one("SELECT COUNT(*) AS n FROM chat_messages")["n"] == 0
        assert c.delete(f"{BASE}/{sid}", headers=ADMIN).status_code == 404
        assert c.get(f"{BASE}/not-a-uuid", headers=ADMIN).status_code == 404
        assert c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "x"}).status_code == 404


def test_missing_owner_setting_is_not_500():
    with TestClient(create_app(settings(chat_owner_id=""))) as c:
        r = c.post(BASE, headers=ADMIN)
        assert r.status_code == 503 and "CHAT_OWNER_ID" in r.json()["detail"]


def test_requires_admin_token():
    with make() as c:
        assert c.post(BASE).status_code == 401


# ---- 요약 항목 · 조회 함수(function calling) ----
def seed_orders(c):
    """KST 2026-10-12(월) 12시에 3만원(생맥주 2개), 2026-10-13(화) 20시에 2만원(소주 1개) 주문을 넣는다."""
    from datetime import datetime
    from app.services.grades import KST
    db = c.app.state.db
    for day, hour, total, menu, qty in ((12, 12, 30000, "생맥주", 2), (13, 20, 20000, "소주", 1)):
        stamp = datetime(2026, 10, day, hour, tzinfo=KST).isoformat()
        oid = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?,?,?)", (1, total, stamp))
        db.run("INSERT INTO order_items (order_id, kind, name, unit_price, qty) VALUES (?,?,?,?,?)",
               (oid, "menu", menu, total // qty, qty))


def service(c):
    from app.services.chat import ChatService
    from app.stores.stats import StatsStore
    return ChatService(settings(),
                       StatsStore(c.app.state.db), c.app.state.members)


def test_summary_has_weekday_hour_menu_and_grades():
    from datetime import date
    with make() as c:
        seed_orders(c)
        text = service(c).summary(date(2026, 10, 14))
    assert "최근 7일 일별" in text and "10/13(화) 매출 20,000원, 주문 1건" in text
    assert "월 30,000원" in text and "화 20,000원" in text  # 요일별
    assert "12시 30,000원" in text  # 시간대별
    assert "생맥주 2개" in text and "현재 품절 메뉴:" in text
    assert "신규" in text and "휴면" in text  # 등급별 회원


def test_run_tool_results_are_computed_by_server():
    with make() as c:
        seed_orders(c)
        s = service(c)
        r = s.run_tool("sales_between", {"start_date": "2026-10-01", "end_date": "2026-10-31"})
        assert r == {"revenue": 50000, "orders": 2, "avg_order": 25000}
        r = s.run_tool("sales_breakdown", {"start_date": "2026-10-01", "end_date": "2026-10-31", "by": "weekday"})
        assert r["groups"]["화"] == {"revenue": 20000, "orders": 1}
        r = s.run_tool("menu_sold", {"menu_name": "맥주", "start_date": "2026-10-01", "end_date": "2026-10-12"})
        assert r["total_qty"] == 2 and r["matched_menus"] == {"생맥주": 2}  # 기간 밖(13일) 소주는 제외
        r = s.run_tool("top_menus", {"start_date": "2026-10-01", "end_date": "2026-10-31", "limit": 1})
        assert r["top"] == [{"name": "생맥주", "qty": 2}]


def test_run_tool_bad_args_return_error_not_exception():
    with make() as c:
        s = service(c)
        assert "error" in s.run_tool("sales_between", {"start_date": "어제", "end_date": "오늘"})
        assert "error" in s.run_tool("sales_between", {"start_date": "2026-10-02", "end_date": "2026-10-01"})
        assert "error" in s.run_tool("sales_breakdown", {"start_date": "2026-10-01", "end_date": "2026-10-02", "by": "x"})
        assert "error" in s.run_tool("drop_table", {"start_date": "2026-10-01", "end_date": "2026-10-02"})


def test_gemini_function_call_loop(monkeypatch):
    """제미나이가 함수 호출을 요청하면 서버가 실행해 결과를 돌려주고, 그 결과를 본 뒤 최종 답을 만든다."""
    sent = []
    replies = iter([
        {"role": "model", "parts": [{"functionCall": {"name": "sales_between", "args": {
            "start_date": "2026-10-01", "end_date": "2026-10-31"}}}]},
        {"role": "model", "parts": [{"text": "10월 매출은 50,000원이에요."}]},
    ])

    def call(self, system, contents):
        sent.append([dict(m) for m in contents])
        return next(replies)
    monkeypatch.setattr(chat_service.ChatService, "_call", call)
    with make(gemini_api_key="k") as c:
        seed_orders(c)
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "10월 매출?"})
    assert r.json()["messages"][1]["content"] == "10월 매출은 50,000원이에요."
    response = sent[1][-1]["parts"][0]["functionResponse"]  # 두 번째 호출에 서버 계산 결과가 실려 갔다
    assert response["name"] == "sales_between" and response["response"]["revenue"] == 50000


def test_gemini_endless_function_calls_stop(monkeypatch):
    loop = {"role": "model", "parts": [{"functionCall": {"name": "top_menus", "args": {
        "start_date": "2026-10-01", "end_date": "2026-10-31"}}}]}
    monkeypatch.setattr(chat_service.ChatService, "_call", lambda self, system, contents: loop)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "?"})
        assert r.status_code == 502


def test_follow_up_question_sends_previous_answer_as_context(monkeypatch):
    """멀티턴: 둘째 질문을 보낼 때 첫 질문(user)과 첫 답변(model)이 제미나이에 함께 전달된다."""
    sent = []

    def call(self, system, contents):
        sent.append(contents)
        return {"role": "model", "parts": [{"text": f"답변{len(sent)}"}]}
    monkeypatch.setattr(chat_service.ChatService, "_call", call)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "저번주 매출?"})
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "그럼 그 전주는?"})
    second = [(m["role"], m["parts"][0]["text"]) for m in sent[1]]
    assert second == [("user", "저번주 매출?"), ("model", "답변1"), ("user", "그럼 그 전주는?")]
