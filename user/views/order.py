"""주문 화면의 조각 (상단 헤더·카테고리·메뉴 목록).
"""

from html import escape

import streamlit as st

from user.state import context as ctx
from user.state.cart import cart_add, cart_count
from user.state.menu_groups import group_spicy_variants
from user.state.quiz import open_quiz
from user.ui.common import mini_buttons, thumb_html, won
from user.ui.dialogs import orders_dialog, staff_dialog
from user.views.ai import render_recommendations


def render_header():
    with st.container(key="header"):
        c_brand, c_table, c_actions, c_mini = st.columns([3.5, 1.2, 3, 1], vertical_alignment="center")
        c_brand.html(f'<div class="brand"><div class="logo">🍺</div><div><div class="name">{ctx.STORE["name"]}</div>'
                     f'<div class="sub">{ctx.STORE["branch"]}{f" · {escape(st.session_state.member["nickname"])}님 (회원)" if st.session_state.member else " · 비회원"}</div></div></div>')
        c_table.html(f'<div class="table-chip">TABLE <b>{st.session_state.table}</b></div>')
        with c_actions.container(horizontal=True, key="header_actions"):
            if st.button("🔔 직원호출", width="stretch"):
                staff_dialog()
            n_orders = len(st.session_state.orders)
            if st.button(f"🧾 주문내역{f' ({n_orders})' if n_orders else ''}", width="stretch"):
                orders_dialog()
        with c_mini:
            mini_buttons("header")


def render_categories():
    st.button("💬 AI 질문", key="open_quiz", width="stretch", type="primary", on_click=open_quiz,
              help="몇 가지 질문에 답하면 메뉴 조합을 추천해 드려요")
    for c in ctx.CATEGORIES:
        if st.button(f"{c['icon']}  {c['name']}", key=f"cat_{c['id']}", width="stretch",
                     type="primary" if st.session_state.cat == c["id"] else "secondary"):
            st.session_state.cat = c["id"]
            st.rerun()


def render_menu():
    cat = st.session_state.cat
    if cat == "ai":
        render_recommendations()
        return
    items = [m for m in ctx.MENU if "BEST" in m["tags"]] if cat == "best" else [m for m in ctx.MENU if m["cat"] == cat]
    category = ctx.CATEGORY_BY_ID[cat]
    entries = group_spicy_variants(items)
    st.html(f'<div class="section-title">{category["icon"]} {category["name"]} <span>{len(entries)}</span></div>')
    with st.container(horizontal=True, key="menu_grid"):
        for entry in entries:
            if entry["type"] == "item":
                _render_card(entry["item"])
            else:
                _render_card(_selected_variant(entry), group=entry)


def _selected_variant(group):
    """그룹에서 지금 선택된 매운맛 단계의 메뉴. 선택 상태는 세션에 보관한다."""
    by_label = dict(group["variants"])
    key = f"spicy_{group['id']}"
    if st.session_state.get(key) not in by_label:
        st.session_state[key] = group["variants"][0][0]
    return by_label[st.session_state[key]]


def _render_card(item, group=None):
    """메뉴 카드 하나. group 이 있으면 가격 아래에 매운맛 선택 버튼을 두고, 선택한 단계의 메뉴를 담는다."""
    qty = cart_count(item["id"]) if group is None else sum(cart_count(m["id"]) for _, m in group["variants"])
    with st.container(key=f"card_{item['id'] if group is None else group['id']}"):
        st.html(thumb_html(item, qty) +
                f'<div class="mname">{item["name"] if group is None else escape(group["name"])}</div>'
                f'<div class="mdesc">{item["desc"]}</div><div class="mprice">{won(item["price"])}</div>')
        if group is not None:
            st.segmented_control("매운맛", [label for label, _ in group["variants"]], key=f"spicy_{group['id']}",
                                 required=True, label_visibility="collapsed", width="stretch")
        if st.button("품절" if item["soldout"] else "담기", key=f"add_{item['id']}", width="stretch",
                     disabled=item["soldout"]):
            cart_add(item, "", item["price"], 1)
            st.rerun()
