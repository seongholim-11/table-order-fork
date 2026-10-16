"""주문·회원 원본 더미 (관리자 주문 목록, 주문 생성). (담당: 재현. members 는 통계 더미도 읽는다)"""

from app.dummy._common import _ago

# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "GET /admin/api/orders": "orders",
    "POST /api/orders": "order_created",
}


def members() -> list[dict]:
    """주문·통계 더미가 쓰는 회원 원본 행. (GET /admin/api/members 는 문자 발송 대상 선택과 이어져 있어 더미가 아니라 DB 를 읽는다)"""
    def m(i, nick, gender, year, visits, last, consent=True, opted=False, phone="010-0000-0000"):
        return {"id": i, "kakao_id": f"dummy-{i}", "nickname": nick, "phone": phone, "gender": gender, "birthday": None,
                "birth_year": year, "marketing_consent": consent, "opted_out": opted, "visit_count": visits,
                "last_visit_at": last, "created_at": _ago(days=90)}
    return [m(1, "민지", "female", 1998, 1, _ago(hours=1)), m(2, "준호", "male", 1990, 3, _ago(days=2)),
            m(3, "서연", "female", 2003, 6, _ago(days=1)), m(4, "도현", "male", 1982, 4, _ago(days=75)),
            m(5, "지우", "female", 1975, 2, _ago(days=10), consent=False, phone=None),
            m(6, "태민", "male", 2008, 1, _ago(days=3), opted=True)]


def orders() -> list[dict]:
    """주문 원본(ts·lines 모양). 최신순."""
    def line(id_, name, unit, qty, **extra):
        return {"id": id_, "name": name, "opt": "", "unit": unit, "qty": qty, **extra}
    combo = line("combo:1", "AI 추천 조합", 31000, 1, components=[
        {"id": "c1", "name": "역전 옛날통닭 (한 마리·후라이드)", "opt": "", "qty": 1}, {"id": "b1", "name": "생맥주 500cc", "opt": "", "qty": 2}])
    rows = [
        (12, 5, 2, 36000, False, _ago(hours=1), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 2)]),
        (11, 3, 1, 31000, True, _ago(hours=2), [combo]),
        (10, 8, 3, 25000, False, _ago(hours=3), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 1), line("s1", "감자튀김", 7000, 1)]),
        (9, 2, None, 18000, False, _ago(days=1), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 1)]),
        (8, 7, 3, 49000, True, _ago(days=1, hours=2), [combo, line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 1)]),
        (7, 4, 2, 54000, False, _ago(days=2), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 3)]),
        (6, 5, 4, 36000, False, _ago(days=3), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 2)]),
        (5, 1, 3, 31000, True, _ago(days=4), [combo]),
        (4, 9, None, 18000, False, _ago(days=5), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 1)]),
        (3, 6, 5, 62000, False, _ago(days=6), [line("c1", "역전 옛날통닭 (한 마리·후라이드)", 18000, 2), combo]),
    ]
    return [{"id": i, "table_no": t, "member_id": mid, "total": total, "roulette_discount_percent": 0,
             "ai_combo": ai, "recommendation_event_id": None, "ts": ts, "lines": lines}
            for i, t, mid, total, ai, ts, lines in rows]


def order_created(coupon_ids: list[int] | None = None) -> dict:
    return {"no": 13, "ai_combo": False, "used_coupon_ids": list(coupon_ids or [])}
