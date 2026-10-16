"""정보 조회(GET) API 의 더미 응답을 한곳에 모아 둔 파일.

팀원이 엔드포인트를 하나씩 실제 DB 로 바꿀 때:
  1. 해당 라우터 함수에서 `dummy.xxx()` 호출을 store/service 호출로 바꾼다.
  2. 이 파일에서 그 함수와 아래 DUMMY_ENDPOINTS 의 줄을 지운다 (다른 엔드포인트는 그대로 둔다).
라우터에서 `dummy.` 로 시작하는 호출이 남아 있으면 아직 더미인 엔드포인트다. (`grep -rn "dummy\\." app/routers`)

QR 로그인(/api/auth/*, /api/members/me, /api/tables/{n}/logins)과 문자 발송(/admin/api/marketing/sms/*)은 더미가 아니다.
고객 목록(GET /admin/api/members)도 문자 발송 대상·수신거부와 같은 회원 id 를 쓰므로 DB 를 그대로 읽는다.
응답 모양은 지금 화면(user/, admin/)이 쓰는 것과 같다. 쓰기(POST/PUT/DELETE)는 그대로 DB 에 저장되지만,
더미 GET 은 그 값을 읽지 않으므로 저장한 결과가 조회에 반영되지 않는다.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SEED = Path(__file__).resolve().parent / "seed"

# 더미인 GET 엔드포인트 목록 (실제 구현으로 바꾸면 이 줄과 아래 함수를 같이 지운다)
DUMMY_ENDPOINTS = {
    "GET /api/store, /api/v1/store": "store",
    "GET /api/content, /api/content/{name}": "content / content_item",
    "GET /api/menus": "menus",
    "GET /api/v1/coupons, /api/coupons": "member_coupons",
    "GET /api/tables/{table_no}/coupons": "table_coupons",
    "GET /admin/api/menus": "admin_menus",
    "GET /admin/api/orders": "orders",
    "GET /admin/api/calls": "calls",
    "GET /admin/api/stats": "dashboard_inputs",
}


def _ago(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat(timespec="seconds")


def _json(name: str):
    return json.loads((_SEED / name).read_text(encoding="utf-8"))


# ---- 사용자 화면 ----
def store() -> dict:
    return {"name": "역전할머니맥주", "branch": "홍대점", "slogan": "옛날 그 맛 그대로, 시원한 생맥주 한 잔!", "tables": 30}


def content() -> dict:
    """카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙. 모양은 seed/content.json 과 같다."""
    return _json("content.json")


def content_item(name: str):
    return content().get(name)


def menus() -> list[dict]:
    """메뉴 전체(품절 포함). 모양은 seed/menu.json 과 같다."""
    return _json("menu.json")


def member_coupons(member_id: int = 1) -> list[dict]:
    return [c for c in _coupons() if c["member_id"] == member_id]


def table_coupons(table_no: int) -> list[dict]:
    return [{**c, "nickname": _MEMBER_NAMES[c["member_id"]], "table_no": table_no} for c in _coupons()]


_MEMBER_NAMES = {1: "민지", 2: "준호", 3: "서연"}


def _coupons() -> list[dict]:
    base = {"table_no": 1, "used_order_id": None, "used_at": None, "item_id": None, "percent": None}
    return [
        {**base, "id": 3, "member_id": 1, "kind": "discount", "label": "10% 할인", "emoji": "🎟️", "percent": 10,
         "issued_at": _ago(hours=1)},
        {**base, "id": 2, "member_id": 2, "kind": "free", "label": "서비스 메뉴", "emoji": "🎁", "item_id": "s1",
         "issued_at": _ago(hours=2)},
        {**base, "id": 1, "member_id": 3, "kind": "discount", "label": "5% 할인", "emoji": "🎟️", "percent": 5,
         "issued_at": _ago(days=1), "used_at": _ago(days=1, hours=-1), "used_order_id": 1},
    ]


# ---- 관리자 화면 ----
def admin_menus() -> dict:
    content_ = content()
    cats = [{"id": c["id"], "name": c["name"]} for c in content_["categories"] if c["id"] not in ("ai", "best")]
    return {"categories": cats, "menus": menus()}


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


def calls() -> list[dict]:
    return [{"id": 3, "ts": _ago(minutes=3), "table_no": 5, "items": ["물", "앞접시"], "done": False},
            {"id": 2, "ts": _ago(minutes=20), "table_no": 3, "items": ["수저"], "done": False},
            {"id": 1, "ts": _ago(hours=2), "table_no": 8, "items": ["물티슈"], "done": True}]


def dashboard_inputs() -> dict:
    """대시보드 통계를 계산할 입력(주문·회원·추천 노출 수). 계산은 services/stats.py 가 한다."""
    return {"orders": orders(), "members": members(), "recommendations": 9}
