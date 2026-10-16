"""화면 전체가 같이 쓰는 세션 상태 (초기화·화면 이동·테마·URL 동기화).
"""

import streamlit as st

from user.state import context as ctx


def init_state():
    ss = st.session_state
    # 새로고침해도 보던 화면으로 돌아오도록 URL(?page=order&cat=...)에서 복원한다. sync_url() 이 반대 방향을 맡는다.
    qp = st.query_params
    ss.setdefault("theme", "light" if qp.get("theme") == "light" else "dark")  # ?theme=light 로 새로고침해도 유지
    ss.setdefault("page", "order" if qp.get("page") == "order" else "splash")
    ss.setdefault("cat", qp.get("cat") if qp.get("cat") in ctx.CATEGORY_BY_ID else "best")
    ss.setdefault("cart", {})        # key -> {id, name, opt, unit, qty}
    ss.setdefault("orders", [])      # 주문 내역
    ss.setdefault("calls", [])
    ss.setdefault("roulette", None)  # {"idx", "angle", "animate"} - 세션당 1회
    ss.setdefault("coupons", [])      # 쿠폰함: 룰렛에서 받은 쿠폰 (user/state/coupons.py)
    ss.setdefault("applied_coupons", [])  # 지금 장바구니에 적용 중인 쿠폰 key
    ss.setdefault("roulette_percent", 0)  # 다음 주문에 적용할 룰렛 할인율
    ss.setdefault("member", None)    # QR 로그인한 회원 {id, nickname}
    ss.setdefault("access_token", None)
    ss.setdefault("quiz", {"step": 0, "answers": {}})  # AI 질문 진행 상태
    ss.setdefault("members", [])      # 이 태블릿에서 로그인한 회원 기록 (누적): {id, nickname, at, eligible, prize}
    ss.setdefault("granted_ids", [])  # 룰렛 기회를 이미 받은 회원 id (회원당 1회)
    ss.setdefault("login", None)     # 발급된 QR 로그인 세션 {token, secret, qr_url, expires_in, created}
    ss.table = table_from_url()


def table_from_url():
    """태블릿마다 다른 QR/주소로 열도록 ?table=번호 를 받는다. 없거나 잘못되면 12번."""
    try:
        n = int(st.query_params.get("table", 12))
    except (TypeError, ValueError):
        n = 12
    return min(max(n, 1), ctx.STORE["tables"])


def go(page):
    st.session_state.page = page


def toggle_theme():
    ss = st.session_state
    ss.theme = "dark" if ss.theme == "light" else "light"


def sync_url():
    """현재 화면을 URL 쿼리에 반영한다 (splash·AI 질문 중에는 주문 화면 기준으로 둔다)."""
    qp = st.query_params
    want = {} if st.session_state.page == "splash" else {"page": "order", "cat": st.session_state.cat}
    if st.session_state.theme == "light":
        want["theme"] = "light"
    for k in ("page", "cat", "theme"):
        if want.get(k) is None:
            qp.pop(k, None)
        elif qp.get(k) != want[k]:
            qp[k] = want[k]
