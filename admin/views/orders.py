"""주문 이력 화면.
"""

from datetime import timedelta

import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head
from order_filters import AI_ALL, AI_CHOICES, filter_orders

ss = st.session_state


ORDER_FILTER_KEYS = ("of_preset", "of_period", "of_tables", "of_keyword", "of_ai", "of_min", "of_max")
PERIOD_PRESETS = ["전체 기간", "오늘", "최근 7일", "최근 30일", "직접 선택"]


def reset_order_filters():
    for key in ORDER_FILTER_KEYS:
        ss.pop(key, None)


def period_bounds(preset, orders, picked):
    """기간 선택 → (시작일, 끝일). 제한이 없으면 (None, None). 기준일은 가장 최근 주문일."""
    last = orders["주문 시각"].max().date()
    days = {"오늘": 0, "최근 7일": 6, "최근 30일": 29}
    if preset in days:
        return last - timedelta(days=days[preset]), last
    if preset == "직접 선택":
        picked = tuple(picked) if isinstance(picked, (tuple, list)) else (picked,)
        if len(picked) == 2:
            return picked
        if len(picked) == 1:
            return picked[0], picked[0]  # 하루만 고르면 그날 하루
    return None, None


def render_order_filters(orders):
    """주문 이력 필터 패널. 조건에 맞는 주문만 돌려준다."""
    with st.container(border=True, key="order_filters"):
        head, clear = st.columns([5, 1.3], vertical_alignment="center")
        head.html('<div class="mcat-title" style="margin:0">🔎 필터</div>')
        lo, hi = orders["주문 시각"].min().date(), orders["주문 시각"].max().date()
        c1, c2, c3 = st.columns([1.2, 1.8, 1.2])
        preset = c1.selectbox("기간", PERIOD_PRESETS, key="of_preset", help="기준일은 가장 최근 주문일이에요")
        picked = None
        if preset == "직접 선택":
            picked = c1.date_input("날짜 범위", value=(lo, hi), min_value=lo, max_value=hi, key="of_period")
        tables = c2.multiselect("테이블", sorted(orders["테이블"].unique()), key="of_tables", placeholder="전체 테이블",
                                format_func=lambda n: f"{n}번")
        ai = c3.selectbox("AI 추천", AI_CHOICES, key="of_ai")
        c4, c5, c6 = st.columns([2, 1, 1])
        keyword = c4.text_input("검색", key="of_keyword", placeholder="닉네임 · 메뉴 이름 · 주문번호")
        min_amount = c5.number_input("최소 금액", 0, step=1000, value=0, key="of_min")
        max_amount = c6.number_input("최대 금액 (0 = 제한 없음)", 0, step=1000, value=0, key="of_max")
        active = preset != PERIOD_PRESETS[0] or tables or keyword.strip() or ai != AI_ALL or min_amount or max_amount
        clear.button("↩ 필터 초기화", key="of_reset", width="stretch", disabled=not active, on_click=reset_order_filters)
    start, end = period_bounds(preset, orders, picked)
    return filter_orders(orders, start=start, end=end, tables=tables, keyword=keyword, ai=ai,
                         min_amount=min_amount or None, max_amount=max_amount or None)


def page_orders(repo, sub="전체 주문"):
    page_head("주문 이력", "기간·테이블·메뉴·금액으로 주문을 골라 볼 수 있어요")
    orders = repo.orders()
    cust = repo.members(ss["grade_rule"]).set_index("customer_id")
    mode = sub  # 전체 주문 / 고객별 주문은 사이드바 하위 메뉴에서 고른다
    if mode == "고객별 주문":
        if cust.empty:
            st.info("아직 회원이 없어요.")
            return
        who = st.selectbox("고객", cust.index, format_func=lambda i: f"{cust.at[i, '닉네임']} ({i}) · {cust.at[i, '등급']}")
        orders = orders[orders["customer_id"] == who]
        st.caption(f"누적 주문 금액 {int(orders['금액'].sum()):,}원")
    if orders.empty:
        st.info("조건에 맞는 주문이 없어요." if mode == "고객별 주문" else "아직 주문이 없어요.")
        return
    shown = render_order_filters(orders)
    total = int(shown["금액"].sum())
    kpi_row(kpi("조회된 주문", len(shown), "건", sub=f"전체 {len(orders)}건 중", accent=True),
            kpi("합계 금액", f"{total:,}", "원"),
            kpi("평균 주문금액", f"{total // len(shown):,}" if len(shown) else "-", "원" if len(shown) else ""),
            kpi("AI 추천 사용", int(shown["AI 추천 사용"].sum()), "건"))
    if shown.empty:
        st.info("조건에 맞는 주문이 없어요. 필터를 바꿔 보세요.")
        return
    with st.container(key="orders_table_cust" if mode == "고객별 주문" else "orders_table"):  # 표 높이는 화면 높이에 맞춰 CSS 가 정한다 (표 안에서만 스크롤)
        st.dataframe(shown, hide_index=True, width="stretch", height="stretch",
                     column_config={"금액": st.column_config.NumberColumn(format="%d원")})
