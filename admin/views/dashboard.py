"""대시보드 화면.
"""

import streamlit as st

from admin.ui.widgets import bars, kpi, kpi_row, page_head, panel, sec_title

ss = st.session_state


def _render_panel_grid(*cards):
    """그래프를 같은 격자에 넣어 열 너비·행 높이·카드 사이 간격을 맞춘다."""
    st.html('<div class="dashboard-panels">' + "".join(cards) + '</div>')


def render_sales_insights(s, x, title="매출", subtitle="오늘 · 최근 7일 · 최근 30일을 한 번에 비교해요"):
    """주문·매출 지표와 매출 그래프만 한 영역에 모아 보여 준다."""
    sec_title(title, subtitle)
    if x["empty"]:
        # 주문 목록이 비어 있어도 서버가 집계한 오늘 주문·평균 금액은 표시한다.
        kpi_row(kpi("오늘 주문", s["today_orders"], "건", accent=True),
                kpi("평균 주문금액", f"{s['avg_order_amount']:,}" if s["today_orders"] else "-",
                    "원" if s["today_orders"] else ""))
        st.html('<div class="empty">아직 주문이 없어요.</div>')
        return
    # 세 카드는 준비된 주문의 마지막 날짜를 시연의 오늘로 삼아 날짜가 지나도 값을 유지한다.
    demo_orders = x.get("last_day_orders", s["today_orders"])
    demo_average = x["last_day_revenue"] // demo_orders if demo_orders else 0
    kpi_row(
        kpi("오늘 주문", demo_orders, "건", accent=True),
        kpi("평균 주문금액", f"{demo_average:,}" if demo_orders else "-", "원" if demo_orders else ""),
        kpi("오늘 매출", f"{x['last_day_revenue']:,}", "원", sub="시연 기준일 주문 합계"),
        kpi("마지막 영업일 매출", f"{x['last_day_revenue']:,}", "원", sub=delta_text(x["last_day_change"], "지난주 같은 요일"), sub_change=x["last_day_change"]),
        kpi("최근 매출 (7일)", f"{x['week_revenue']:,}", "원", sub=delta_text(x["week_change"], "지난 7일"), sub_change=x["week_change"]),
        kpi("최근 매출 (30일)", f"{x['revenue']:,}", "원", sub=f"하루 평균 {x['daily_revenue']:,}원"),
        min_width=150,
    )
    kpi_row(
        kpi("테이블 회전율", x["turnover_avg"], "회/일", sub=f"테이블 {x['tables']}개 · 마지막 영업일 {x['turnover_today']}회"),
        kpi("최근 평균 객단가", f"{x['avg_ticket']:,}", "원", sub=f"최근 주문 {x['orders']:,}건 기준"),
        min_width=180,
    )
    _render_panel_grid(
        panel("시간대별 매출", f"가장 바쁜 시간은 {x['peak_hour']}", bars(x["by_hour"], "원")),
        panel("요일별 매출", f"매출이 가장 높은 요일은 {x['peak_weekday']}요일", bars(x["by_weekday"], "원")),
        panel("일별 매출 (최근 14일)", "하루 매출 흐름", bars(x["by_day"], "원")),
        panel("주문 금액대 분포", "한 번에 얼마씩 주문하는지", bars(x["ticket_bands"], "건")),
    )


def render_order_customers(x, s):
    """고객 분석: 주문 고객 등급·테이블별 주문, 연령대·성별."""
    sec_title("고객", "오늘 방문 고객과 마지막 영업일의 매출을 함께 확인해요")
    # 주문 목록 더미의 유무와 관계없이 서버의 오늘 고객 집계를 표시한다.
    kpi_row(kpi("오늘 신규 고객", s["new_customers"], "명", accent=True),
            kpi("오늘 재방문 고객", s["returning_customers"], "명"))
    if not x["empty"]:
        member_sub = f"회원 {x['member_revenue']:,}원 · 비회원 {x['guest_revenue']:,}원"
        kpi_row(
            kpi("재방문 고객 비율", f"{x['returning_share']:.0%}" if x["returning_share"] is not None else "-",
                sub="최근 주문 고객 중 재방문·단골"),
            kpi("마지막 영업일 회원 매출 비중", f"{x['member_revenue_share']:.0%}" if x["member_revenue_share"] is not None else "-",
                sub=member_sub),
            min_width=150,
        )
    cards = []
    if not x["empty"]:
        cards.extend([
            panel("고객 등급별 주문 고객", "최근 주문한 고객 수", bars(x["customer_grades"], "명")),
            panel("마지막 영업일 주문 테이블 TOP 5", "마지막 영업일 주문 건수 기준", bars(x["top_tables"], "건", ranked=True)),
        ])
    _render_panel_grid(
        *cards,
        panel("고객 연령대", "출생연도를 입력한 회원만 집계해요", bars(s["age_groups"], "명")),
        panel("고객 성별", "회원 정보 기준", bars(s["genders"], "명")),
    )


def delta_text(change, base):
    """증감률을 '▲ 12% (지난주 대비)' 형태로 (비교 대상이 없으면 안내 문구)."""
    if change is None:
        return f"{base} 데이터가 없어요"
    return f"{'▲' if change >= 0 else '▼'} {abs(change):.0%} ({base} 대비)"


def render_trend_insights(x, popular_menus=None):
    """기존 호출 호환용: 매출 추이 그래프만 보여 준다."""
    if x["empty"]:
        return
    sec_title("매출 추이", "일별 매출과 주문 금액대를 확인해요")
    kpi_row(
        kpi("최근 7일 매출", f"{x['week_revenue']:,}", "원", sub=delta_text(x["week_change"], "지난 7일"), accent=True, sub_change=x["week_change"]),
        kpi("마지막 영업일 매출", f"{x['last_day_revenue']:,}", "원", sub=delta_text(x["last_day_change"], "지난주 같은 요일"), sub_change=x["last_day_change"]),
        kpi("최근 30일 매출", f"{x['revenue']:,}", "원", sub=f"하루 평균 {x['daily_revenue']:,}원"),
    )
    _render_panel_grid(
        panel("일별 매출 (최근 14일)", "하루 매출 흐름", bars(x["by_day"], "원")),
        panel("주문 금액대 분포", "한 번에 얼마씩 주문하는지", bars(x["ticket_bands"], "건")),
    )
    if popular_menus is not None:
        # 첫 화면에서 매출 흐름을 본 다음 바로 인기 메뉴를 확인할 수 있도록 기존 패널을 그대로 한 번 더 보여 준다.
        st.html(panel("인기 메뉴 TOP 10", "주문 수량 기준",
                      bars({menu["name"]: menu["qty"] for menu in popular_menus}, "개", ranked=True,
                           empty="아직 주문이 없어요.")))


def render_menu_stock(repo):
    """고객 정보는 고객 목록에 두고 이 화면에는 현재 메뉴 품절만 표시한다."""
    sec_title("메뉴 판매 현황")
    alerts = repo.menu_alerts()
    names = ", ".join(alerts["sold_out"][:4]) + (f" 외 {len(alerts['sold_out']) - 4}개" if len(alerts["sold_out"]) > 4 else "")
    cards = [
        kpi("품절 메뉴", len(alerts["sold_out"]), "개", sub=names or "품절 메뉴가 없어요"),
        kpi("품절된 인기 메뉴", len(alerts["popular_sold_out"]), "개",
            sub=", ".join(alerts["popular_sold_out"]) or "품절된 인기 메뉴가 없어요"),
    ]
    kpi_row(*cards, min_width=120)


def render_today_sales(s, x):
    """기존 호출 이름을 유지하면서 매출 전용 영역을 그린다."""
    render_sales_insights(s, x)


def page_dashboard(repo, sub="한눈에 보기"):
    """첫 화면은 오늘·매출과 매출 추이를 함께 보여 주고, 상세 영역은 사이드바에서 따로 볼 수 있다."""
    # 전용 컨테이너 안에서만 간격을 조정해 다른 담당자의 화면에는 영향을 주지 않는다.
    with st.container(key="dashboard_layout"):
        _render_dashboard(repo, sub)


def _render_dashboard(repo, sub):
    """대시보드 전용 간격 설정이 적용되는 영역에 기존 화면을 그린다."""
    s = repo.stats(ss["grade_rule"])
    ai = s["ai"]
    # 회전율의 분모는 주문이 발생한 테이블 수가 아니라 매장에 등록된 전체 테이블 수여야 한다.
    x = repo.sales_insights(ss["grade_rule"])
    page_head("대시보드", "오늘 매장 현황을 한눈에 확인하세요")
    if not x["empty"] and x.get("last_order_date"):
        # 화면의 오늘 주문·매출도 준비된 시연 데이터의 날짜를 기준으로 안내한다.
        st.caption(f"시연 기준일은 마지막 주문일 {x['last_order_date']}이며, 주문·매출 카드와 최근 30일 통계에 같은 기준을 사용해요.")
    st.button("🔄 최신 주문 반영", key="dashboard_refresh", help="현재까지 들어온 주문으로 대시보드 전체를 다시 계산해요")
    if sub == "한눈에 보기":
        render_today_sales(s, x)
        render_order_customers(x, s)
        sec_title("메뉴", "오늘 운영에 참고할 인기 메뉴예요")
        st.html(panel("인기 메뉴 TOP 10", "주문 수량 기준",
                      bars({menu["name"]: menu["qty"] for menu in s["popular_menus"]}, "개", ranked=True,
                           empty="아직 주문이 없어요.")))
    elif sub == "오늘 · 매출":
        render_today_sales(s, x)
    elif sub == "매출 추이":
        render_trend_insights(x)
    elif sub == "고객 분석":
        render_order_customers(x, s)
    else:  # 메뉴
        # 메뉴 화면도 같은 격자를 사용하고 AI 카드는 한 묶음으로 배치해 간격을 맞춘다.
        ai_cards = [
            kpi("AI 추천 적중률", f"{ai['hit_rate']:.0%}" if ai["hit_rate"] is not None else "-",
                sub=ai["definition"]),
            kpi("추천 노출", ai["recommendations"], "회", sub=f"조합이 포함된 주문 {ai['ai_orders']}건"),
        ]
        if not x["empty"]:
            # AI·일반 주문 중 한쪽만 있어도 집계된 객단가는 표시하고 없는 쪽은 '-'로 구분한다.
            ai_cards.extend([
                kpi("AI 추천 주문 객단가", f"{x['ai_avg_ticket']:,}" if x["ai_avg_ticket"] is not None else "-",
                    "원" if x["ai_avg_ticket"] is not None else "", sub=f"최근 30일 주문의 {x['ai_share']:.0%}"),
                kpi("일반 주문 객단가", f"{x['plain_avg_ticket']:,}" if x["plain_avg_ticket"] is not None else "-",
                    "원" if x["plain_avg_ticket"] is not None else "", sub="최근 30일 주문 기준"),
            ])
        _render_panel_grid(
            panel("인기 메뉴 TOP 10", "주문 수량 기준",
                  bars({m["name"]: m["qty"] for m in s["popular_menus"]}, "개", ranked=True, empty="아직 주문이 없어요.")),
            '<div class="dashboard-menu-kpis">' + "".join(ai_cards) + '</div>',
        )
        render_menu_stock(repo)
