"""석원 TODO 3: DB 기반 관리자 마케팅 추천 API 테스트."""

from datetime import datetime, timedelta

from app.services.grades import KST
from tests.conftest import ADMIN, login, set_profile

URL = "/admin/api/marketing/opportunities"
GROWTH_URL = "/admin/api/marketing/growth-performance"


def test_empty_data_returns_one_guide_card_and_requires_admin(client):
    assert client.get(URL).status_code == 401
    result = client.get(URL, headers=ADMIN).json()
    assert [{key: card[key] for key in ("title", "why", "action")} for card in result["items"]] == [{
            "title": "데이터를 더 모아 볼까요?",
            "why": "아직 주문·회원 데이터가 적어 추천할 근거가 부족해요.",
            "action": "주문이 쌓이면 이곳에 맞춤 마케팅 방법이 나타나요.",
        }]
    assert result["page"] == result["pages"] == 1
    assert result["groups"]["sms"]["items"] == []
    assert result["groups"]["guide"]["items"] == result["items"]
    assert result["summary"]["members"]["total"] == 0
    assert result["summary"]["orders"] == {
        "count": 0, "revenue": 0, "avg": 0, "peak_hours": [], "top_items": []}
    assert client.get(f"{URL}?round=-1", headers=ADMIN).status_code == 422


def test_cards_use_db_facts_and_round_cycles_four_at_a_time(client):
    """여러 규칙이 켜지는 DB 자료를 넣어 다음 묶음과 처음 순환까지 확인한다."""
    now = datetime.now(KST)
    profiles = [
        ("휴면손님", 2, now - timedelta(days=40), True),
        ("단골손님", 7, now, True),
        ("신규손님", 1, now, False),
    ]
    member_ids = []
    for nickname, visits, last_visit, consent in profiles:
        headers = login(client, nickname, agree=consent)
        member_id = client.get("/api/members/me", headers=headers).json()["id"]
        set_profile(client, headers, phone="01000000000", consent=consent)
        client.app.state.db.run(
            "UPDATE members SET visit_count=?, last_visit_at=? WHERE id=?",
            (visits, last_visit.isoformat(), member_id),
        )
        member_ids.append(member_id)

    db = client.app.state.db
    db.run(
        "INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?, ?, ?, ?, ?)",
        (3, member_ids[1], 18000, 1, now.replace(hour=19).isoformat()),
    )
    order_id = db.one("SELECT MAX(id) AS id FROM orders")["id"]
    db.run(
        "INSERT INTO order_items (order_id, menu_id, kind, name, option_label, unit_price, qty) "
        "VALUES (?, ?, 'menu', ?, '', ?, ?)",
        (order_id, "c1", "역전 옛날통닭", 18000, 1),
    )
    db.run("UPDATE menus SET is_soldout=1 WHERE id='a11'")
    for _ in range(10):
        db.run("INSERT INTO recommendation_events (table_no) VALUES (3)")

    first = client.get(f"{URL}?round=0", headers=ADMIN).json()
    second = client.get(f"{URL}?round=1", headers=ADMIN).json()
    wrapped = client.get(f"{URL}?round={first['pages']}", headers=ADMIN).json()

    assert first["pages"] >= 2 and len(first["items"]) == len(second["items"]) == 4
    assert first["items"] != second["items"] and wrapped["items"] == first["items"]
    assert all({"title", "why", "action", "action_type", "target_grades", "member_ids", "sms_body"} <= set(card)
               for card in first["items"] + second["items"])
    assert any("휴면" in card["title"] and "1명" in card["title"] for card in first["items"] + second["items"])
    assert first["summary"]["members"]["total"] == 3
    assert first["summary"]["members"]["sendable"] == 2
    assert first["summary"]["orders"]["revenue"] == 18000
    # 실제 API에서도 발송 대상이 있는 문자와 현장 활용 추천을 별도로 내려준다.
    assert all(card["action_type"] == "sms" and card["member_ids"]
               for card in first["groups"]["sms"]["items"])
    assert all(card["action_type"] == "guide" and not card["sms_body"]
               for card in first["groups"]["guide"]["items"])


def test_summary_reflects_one_thousand_db_members_and_real_sendable_rule(client):
    """DB에 대량 회원이 추가돼도 전체·발송 가능 숫자를 누락 없이 다시 집계한다."""
    db = client.app.state.db
    for index in range(1000):
        # 절반만 전화번호가 있으므로 수신 동의가 모두 true여도 발송 가능은 500명이어야 한다.
        now = datetime.now(KST).isoformat()
        db.run(
            "INSERT INTO members (kakao_id, nickname, phone, marketing_consent, visit_count, last_visit_at, created_at) "
            "VALUES (?, ?, ?, 1, 1, ?, ?)",
            (f"bulk-{index}", f"대량고객{index}", "01000000000" if index % 2 == 0 else None, now, now),
        )

    summary = client.get(URL, headers=ADMIN).json()["summary"]
    assert summary["members"]["total"] == 1000
    assert summary["members"]["sendable"] == 500
    assert summary["orders"]["count"] == summary["orders"]["revenue"] == 0


def test_growth_performance_uses_db_and_one_month_formula(client):
    """화면 더미가 아니라 orders DB의 최초 AI 주문 전후를 같은 30일 기준으로 계산한다."""
    assert client.get(GROWTH_URL).status_code == 401
    db = client.app.state.db
    start = datetime.now(KST).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=3)
    for offset, amount, ai in ((0, 100, 0), (1, 100, 0), (2, 200, 1), (3, 200, 1)):
        db.run("INSERT INTO orders (table_no, total, ai_combo, created_at) VALUES (1, ?, ?, ?)",
               (amount, ai, (start + timedelta(days=offset)).isoformat()))
    result = client.get(GROWTH_URL, headers=ADMIN).json()
    assert result["baseline_monthly"] == 3_000
    assert result["performance_monthly"] == 6_000
    assert result["monthly_growth"] == 3_000
    assert result["ai_monthly_revenue"] == 6_000
    assert result["monthly_growth"] == result["performance_monthly"] - result["baseline_monthly"]



def _result():
    """제미나이 다듬기 테스트용 추천 결과 (문자 1장 + 기타 1장)."""
    sms = {"title": "휴면 되찾기", "why": "오래 안 왔어요", "action": "문자 보내기", "action_type": "sms",
           "sms_body": "원래 문구", "member_ids": [1], "target_grades": ["휴면"]}
    guide = {"title": "인기 메뉴", "why": "1위예요", "action": "앞세우기", "action_type": "guide",
             "sms_body": "", "member_ids": [], "target_grades": []}
    return {"items": [sms, guide], "groups": {"sms": {"items": [sms]}, "guide": {"items": [guide]}}}


def test_refine_with_gemini_batches_once_caches_and_falls_back(monkeypatch):
    """키가 없으면 규칙 문구 그대로, 있으면 한 번만 호출해 다듬고, 실패하면 규칙 문구로 돌아간다."""
    from types import SimpleNamespace
    from app.services import opportunities as service

    service._REFINE_CACHE.clear()
    calls = []
    monkeypatch.setattr(service, "_ask_gemini_batch",
                        lambda settings, cards: calls.append(cards) or {0: "AI 문자", 1: "AI 할 일"})
    # 키가 없으면 호출하지 않고 source 만 rule 로 붙는다.
    plain = service.refine_with_gemini(_result(), SimpleNamespace(gemini_api_key="", gemini_model="m"))
    assert not calls and plain["items"][0]["source"] == "rule" and plain["items"][0]["sms_body"] == "원래 문구"
    # 키가 있으면 묶음 한 번으로 문자 본문·할 일이 바뀐다. 같은 입력을 다시 보내도 호출하지 않는다.
    settings = SimpleNamespace(gemini_api_key="k", gemini_model="m")
    for _ in range(2):
        refined = service.refine_with_gemini(_result(), settings)
    assert len(calls) == 1
    assert refined["items"][0]["sms_body"] == "AI 문자" and refined["items"][1]["action"] == "AI 할 일"
    assert refined["items"][0]["source"] == "ai"
    # 호출이 실패하면 규칙 문구를 그대로 쓴다.
    service._REFINE_CACHE.clear()
    monkeypatch.setattr(service, "_ask_gemini_batch", lambda s, c: (_ for _ in ()).throw(ValueError("x")))
    failed = service.refine_with_gemini(_result(), settings)
    assert failed["items"][0]["sms_body"] == "원래 문구" and failed["items"][0]["source"] == "rule"


def test_refresh_regenerates_instead_of_using_cache(monkeypatch):
    """재추천(refresh)이면 같은 입력이라도 제미나이를 다시 불러 새 문구를 받는다."""
    from types import SimpleNamespace
    from app.services import opportunities as service

    service._REFINE_CACHE.clear()
    answers = iter([{0: "첫 문구", 1: "첫 할 일"}, {0: "새 문구", 1: "새 할 일"}])
    monkeypatch.setattr(service, "_ask_gemini_batch", lambda settings, cards: next(answers))
    settings = SimpleNamespace(gemini_api_key="k", gemini_model="m")
    assert service.refine_with_gemini(_result(), settings)["items"][0]["sms_body"] == "첫 문구"
    assert service.refine_with_gemini(_result(), settings)["items"][0]["sms_body"] == "첫 문구"  # 캐시
    assert service.refine_with_gemini(_result(), settings, refresh=True)["items"][0]["sms_body"] == "새 문구"
    assert service.refine_with_gemini(_result(), settings)["items"][0]["sms_body"] == "새 문구"  # 새 결과가 캐시됨


def test_live_activity_changes_when_login_or_order_arrives(client):
    """폴링용 조회: 새 로그인·주문이 생기면 번호가 늘고 최근 사건에 나온다."""
    url = "/admin/api/marketing/live-activity"
    assert client.get(url).status_code == 401
    before = client.get(url, headers=ADMIN).json()
    assert before["login_id"] == before["order_id"] == 0 and before["recent"] == []
    headers = login(client, "폴링손님", agree=True)
    member_id = client.get("/api/members/me", headers=headers).json()["id"]
    client.app.state.db.run(
        "INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?, ?, ?, ?, ?)",
        (7, member_id, 9000, 0, datetime.now(KST).isoformat()))
    after = client.get(url, headers=ADMIN).json()
    assert after["login_id"] > before["login_id"] and after["order_id"] > before["order_id"]
    assert {event["kind"] for event in after["recent"]} == {"login", "order"}
    assert any(event["kind"] == "order" and event["table_no"] == 7 and event["nickname"] == "폴링손님"
               for event in after["recent"])
