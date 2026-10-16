"""쿠폰함·룰렛 당첨 더미. (담당: 재현)"""

from app.dummy._common import _ago

# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "GET /api/v1/coupons, /api/coupons": "member_coupons",
    "GET /api/tables/{table_no}/coupons": "table_coupons",
    "PUT /api/tables/{table_no}/logins/prize": "prize_saved",
}


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


def prize_saved(prize: str, kind: str | None, emoji: str, percent: int | None, item_id: str | None) -> dict:
    """룰렛 당첨 저장 결과. 쿠폰 종류를 함께 보냈으면 방금 발급된 것처럼 쿠폰 한 장을 돌려준다."""
    coupon = None
    if kind:
        coupon = {"id": 4, "member_id": 1, "table_no": 1, "kind": kind, "label": prize, "emoji": emoji,
                  "percent": percent, "item_id": item_id, "issued_at": _ago(seconds=0), "used_at": None,
                  "used_order_id": None}
    return {"ok": True, "coupon": coupon}
