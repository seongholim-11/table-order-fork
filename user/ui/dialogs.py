"""다이얼로그 (주문 확인·주문내역·직원 호출).
"""

import time
from datetime import datetime

import streamlit as st

from user.state import context as ctx
from user.state.cart import cart_discount, cart_total, roulette_discount
from user.state.coupons import consume_applied, pending_coupon_ids
from user.ui.common import KST, won


@st.dialog("주문 확인", width="medium")
def confirm_dialog():
    cart = st.session_state.cart
    for l in cart.values():
        opt = f" ({l['opt']})" if l["opt"] else ""
        st.html(f'<div class="order-item"><span>{l["name"]}{opt} × {l["qty"]}</span>'
                    f'<span>{won(l["unit"] * l["qty"])}</span></div>')
    st.divider()
    if cart_discount():
        st.caption(f"AI 조합 할인 −{won(cart_discount())} 적용")
    if roulette_discount():
        st.caption(f"쿠폰 {st.session_state.roulette_percent}% 할인 −{won(roulette_discount())} 적용")
    st.html(f'<div class="total-row"><span>총 주문금액</span><b>{won(cart_total())}</b></div>')
    st.caption("주문 후에는 취소가 어려우니 직원에게 문의해 주세요.")
    with st.container(key="dialog_actions"):
        c1, c2 = st.columns(2, wrap=False)
    if c1.button("돌아가기", width="stretch"):
        st.rerun()
    if c2.button("주문하기", type="primary", width="stretch"):
        no = len(st.session_state.orders) + 1
        server_no = ctx.REPO.create_order(st.session_state.table, [dict(l) for l in cart.values()], cart_total(),
                                      st.session_state.access_token, pending_coupon_ids())
        consume_applied()  # 쿠폰함에서 적용한 쿠폰을 사용 처리 (룰렛 할인율도 함께 초기화)
        no = server_no or no  # 서버가 주문번호를 주면 그것을 쓴다
        st.session_state.orders.append({"no": no, "ts": time.time(), "time": datetime.now(KST).strftime("%H:%M"),
                                        "lines": list(cart.values()), "total": cart_total(),
                                        "member": (st.session_state.member or {}).get("nickname")})
        st.session_state.cart = {}
        st.toast(f"주문이 접수되었습니다 (주문번호 #{no})", icon="✅")
        st.rerun()


@st.dialog("주문내역", width="large")
def orders_dialog():
    orders = st.session_state.orders
    if not orders:
        st.html('<div class="cart-empty">아직 주문 내역이 없어요</div>')
        return
    for o in reversed(orders):
        rows = "".join(
            f'<div class="order-item"><span>{l["name"]}{" (" + l["opt"] + ")" if l["opt"] else ""} × {l["qty"]}</span>'
            f'<span>{won(l["unit"] * l["qty"])}</span></div>' for l in o["lines"])
        st.html(f'<div class="order-box"><div class="order-head"><span>주문 #{o["no"]} · {o["time"]}</span>'
                    f'</div>{rows}'
                    f'<div class="order-item" style="margin-top:6px;font-weight:800;color:#ffb703"><span>소계</span><span>{won(o["total"])}</span></div></div>')
    st.html(f'<div class="total-row"><span>누적 주문금액</span><b>{won(sum(o["total"] for o in orders))}</b></div>')


@st.dialog("직원 호출", width="medium")
def staff_dialog():
    picks = st.pills("필요한 항목을 선택해 주세요", ctx.STAFF_CALLS, selection_mode="multi")
    if st.button("호출하기", type="primary", width="stretch", disabled=not picks):
        ctx.REPO.create_call(st.session_state.table, list(picks))
        st.session_state.calls.append((datetime.now(KST).strftime("%H:%M"), picks))
        st.toast("직원이 곧 도착합니다 🙋", icon="🔔")
        st.rerun()
