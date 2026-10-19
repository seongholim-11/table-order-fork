"""쿠폰함 팝업: 룰렛에서 받은 쿠폰을 보고, 주문에 쓸 쿠폰을 장바구니에 적용한다."""

from html import escape

import streamlit as st

from user.state.coupons import apply_coupon, cancel_coupon, is_applied, load_coupons, usable


def _benefit(c: dict) -> str:
    return f"전 메뉴 {c['percent']}% 할인" if c["kind"] == "discount" else f"{c['label']}"


def _change(action, key: str) -> None:
    """쿠폰 사용/취소를 처리하고, 팝업이 화면 전체 새로고침을 하도록 표시를 남긴다."""
    action(key)
    st.session_state.coupon_changed = True


@st.dialog("쿠폰함", width="medium")
def coupons_dialog():
    ss = st.session_state
    if not ss.members:
        st.html('<div class="cart-empty">로그인하고 룰렛을 돌리면 쿠폰이 여기에 담겨요</div>')
        return
    load_coupons()
    live = usable()
    if not ss.coupons:
        st.html('<div class="cart-empty">아직 받은 쿠폰이 없어요<br>룰렛에서 당첨되면 이곳에 담겨요</div>')
        return
    st.caption(f"사용할 수 있는 쿠폰 {len(live)}장 · 사용을 누르면 장바구니에 적용되고, 주문하면 사용 처리돼요")
    for c in sorted(ss.coupons, key=lambda c: c["used"]):
        applied = is_applied(c["key"])
        state = "사용 완료" if c["used"] else "적용 중" if applied else "사용 가능"
        with st.container(key=f"coupon_{c['key']}", horizontal=True, vertical_alignment="center"):
            st.html(f'<div class="order-item" style="flex:1;opacity:{0.5 if c["used"] else 1}">'
                    f'<span>{escape(c["emoji"])} <b>{escape(_benefit(c))}</b>'
                    f'<br><small>{escape(c["nickname"])}님 · {state}</small></span></div>')
            if c["used"]:
                continue
            if applied:
                st.button("취소", key=f"coupon_cancel_{c['key']}", on_click=_change, args=(cancel_coupon, c["key"]))
            else:
                st.button("사용", key=f"coupon_use_{c['key']}", type="primary", on_click=_change, args=(apply_coupon, c["key"]))
    # 팝업 안의 버튼은 팝업만 다시 그리므로, 쿠폰이 바뀌었으면 화면 전체를 다시 그려(st.rerun) 장바구니에 바로 반영한다
    if ss.pop("coupon_changed", False):
        st.rerun()
