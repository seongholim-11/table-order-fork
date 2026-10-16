"""장바구니 패널.
"""

import streamlit as st

from user.state.cart import cart_change, cart_count, cart_discount, cart_remove, cart_total, roulette_discount
from user.ui.common import won


def render_cart(dialog=False):
    cart = st.session_state.cart
    with st.container(key="dialog_cart_panel" if dialog else "cart_panel"):
        st.html(f'<div class="cart-title">🛒 장바구니 <span>{cart_count()}</span></div>')
        with st.container(key="dialog_cart_items" if dialog else "cart_items"):
            if not cart:
                st.html('<div class="cart-empty"><span class="emoji">🍻</span>메뉴를 담아주세요</div>')
            for key, l in list(cart.items()):
                st.html(f'<div class="cart-line"><div><div class="n">{l["name"]}</div>'
                            f'<div class="o">{l["opt"]}</div></div><div class="p">{won(l["unit"] * l["qty"])}</div></div>')
                c1, c2, c3, c4 = st.columns(4, vertical_alignment="center", wrap=False)
                prefix = "dialog_" if dialog else ""
                c1.button("−", key=f"q_{prefix}dec_{key}", help=f"{l['name']} 수량 줄이기", width="stretch", on_click=cart_change, args=(key, -1))
                c2.html(f'<div class="quantity">{l["qty"]}</div>')
                c3.button("+", key=f"q_{prefix}inc_{key}", help=f"{l['name']} 수량 늘리기", width="stretch", on_click=cart_change, args=(key, 1))
                c4.button("🗑", key=f"q_{prefix}del_{key}", help=f"{l['name']} 삭제", width="stretch", on_click=cart_remove, args=(key,))
                st.divider()
        if cart_discount():
            st.html(f'<div class="cart-savings">✨ AI 조합으로 {won(cart_discount())} 할인받았어요</div>')
        if roulette_discount():
            st.html(f'<div class="cart-savings">🎟️ 쿠폰 {st.session_state.roulette_percent}% 할인 −{won(roulette_discount())}</div>')
        st.html(f'<div class="total-row"><span>총 주문금액</span><b>{won(cart_total())}</b></div>')
        if st.button("주문 확인하기", type="primary", width="stretch", key="dialog_order_btn" if dialog else "order_btn", disabled=not cart):
            st.session_state.confirm_order = True
            st.rerun()
