"""쿠폰함 상태 (룰렛에서 받은 쿠폰의 보관·적용·사용 처리).

룰렛에 당첨되면 바로 장바구니에 반영하지 않고 쿠폰함에 넣는다. 손님이 쿠폰함에서 '사용'을 누르면
장바구니에 적용(할인율 설정 또는 서비스 메뉴 담기)되고, 주문이 접수될 때 쿠폰이 사용 처리된다.
서버에서 받은 쿠폰은 id 가 있고, 서버가 안 닿을 때 받은 쿠폰은 id=None 인 이 세션 안의 쿠폰이다.
"""

import streamlit as st

import server
from user.state import context as ctx
from user.state.cart import cart_add, cart_change

FREE_OPT = "룰렛 서비스"  # 서비스 쿠폰으로 담은 장바구니 줄의 옵션 이름


def _key(c: dict) -> str:
    return str(c["id"]) if c.get("id") else f"local-{c['n']}"


def _entry(c: dict, nickname: str) -> dict:
    return {"id": c.get("id"), "n": c.get("n"), "key": _key(c), "member_id": c.get("member_id"), "nickname": nickname,
            "kind": c["kind"], "label": c["label"], "emoji": c.get("emoji", "🎁"), "percent": c.get("percent"),
            "item_id": c.get("item_id"), "used": bool(c.get("used_at"))}


def add_coupon(member_id: int, nickname: str, prize: dict, server_coupon: dict | None) -> None:
    """룰렛 당첨 결과를 쿠폰함에 넣는다. server_coupon 이 없으면(서버 미연결) 이 세션에만 둔다."""
    ss = st.session_state
    base = server_coupon or {"n": len(ss.coupons) + 1, "member_id": member_id, "kind": prize["kind"],
                             "label": prize["short"], "emoji": prize.get("emoji", "🎁"),
                             "percent": prize.get("percent"), "item_id": prize.get("item_id")}
    ss.coupons.append(_entry(base, nickname))


def load_coupons() -> None:
    """서버의 쿠폰함(이 태블릿에 로그인한 회원들의 쿠폰)을 다시 읽는다. 서버에 없는 세션 쿠폰은 그대로 둔다."""
    ss = st.session_state
    rows = server.table_coupons(ss.access_token, ss.table) if ss.access_token else None
    if rows is None:
        return
    applied = set(ss.applied_coupons)
    ss.coupons = [c for c in ss.coupons if c["id"] is None] + [
        {**_entry(r, r["nickname"]), "used": bool(r["used_at"])} for r in rows]
    ss.applied_coupons = [k for k in ss.applied_coupons if k in applied and any(c["key"] == k and not c["used"] for c in ss.coupons)]


def usable() -> list[dict]:
    return [c for c in st.session_state.coupons if not c["used"]]


def _find(key: str) -> dict | None:
    return next((c for c in st.session_state.coupons if c["key"] == key), None)


def _sync_percent() -> None:
    """적용 중인 할인 쿠폰의 할인율을 장바구니 계산(roulette_percent)에 반영한다."""
    ss = st.session_state
    ss.roulette_percent = max([c["percent"] for k in ss.applied_coupons if (c := _find(k)) and c["kind"] == "discount"],
                              default=0)


def is_applied(key: str) -> bool:
    return key in st.session_state.applied_coupons


def apply_coupon(key: str) -> None:
    ss = st.session_state
    c = _find(key)
    if not c or c["used"] or key in ss.applied_coupons:
        return
    if c["kind"] == "discount":  # 할인 쿠폰은 한 번에 하나만 적용한다 (다른 것이 적용돼 있으면 바꾼다)
        for k in [k for k in ss.applied_coupons if (o := _find(k)) and o["kind"] == "discount"]:
            ss.applied_coupons.remove(k)
    elif c["item_id"] in ctx.MENU_BY_ID:
        cart_add(ctx.MENU_BY_ID[c["item_id"]], FREE_OPT, 0, 1)
    else:
        st.toast("지금은 이 서비스 메뉴를 쓸 수 없어요.", icon="🙏")
        return
    ss.applied_coupons.append(key)
    _sync_percent()


def cancel_coupon(key: str) -> None:
    ss = st.session_state
    c = _find(key)
    if key not in ss.applied_coupons:
        return
    ss.applied_coupons.remove(key)
    if c and c["kind"] == "free":
        cart_change(f"{c['item_id']}|{FREE_OPT}", -1)
    _sync_percent()


def consume_applied() -> list[int]:
    """주문이 접수됐을 때 호출: 적용했던 쿠폰을 사용 처리하고, 서버에 알릴 쿠폰 id 를 돌려준다.
    서비스 쿠폰은 장바구니에서 그 메뉴를 뺐으면 쓰지 않은 것으로 본다."""
    ss = st.session_state
    ids = []
    for k in ss.applied_coupons:
        c = _find(k)
        if not c or (c["kind"] == "free" and f"{c['item_id']}|{FREE_OPT}" not in ss.cart):
            continue
        c["used"] = True
        if c["id"]:
            ids.append(c["id"])
    ss.applied_coupons = []
    ss.roulette_percent = 0
    return ids


def pending_coupon_ids() -> list[int]:
    """지금 장바구니에 적용돼 있는 쿠폰 중 서버 id 가 있는 것 (주문 요청에 실어 보낸다)."""
    ss = st.session_state
    out = []
    for k in ss.applied_coupons:
        c = _find(k)
        if c and c["id"] and not (c["kind"] == "free" and f"{c['item_id']}|{FREE_OPT}" not in ss.cart):
            out.append(c["id"])
    return out
