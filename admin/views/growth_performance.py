"""마케팅 > F&B그로스 성과 화면.

기존 매출·고객 데이터를 한곳에 모으고, 주문의 ``AI 추천 사용`` 기록으로 확인 가능한
성과만 계산한다. 과거 고객 등급이 필요한 지표는 임의로 추측하지 않고 준비 상태로 표시한다.
"""

import altair as alt
import pandas as pd
import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head, sec_title
from admin.views.dashboard import render_sales_insights
from dashboard_stats import recent_orders


def growth_summary(orders: pd.DataFrame, members: pd.DataFrame) -> dict:
    """최초 AI 주문 전후를 같은 월환산 기준으로 비교한다.

    # DB 연동: API 모드에서는 backend/app/services/growth_performance.py가
    # orders·members 테이블을 읽어 같은 필드와 계산식으로 응답한다.
    """
    recent = recent_orders(orders)
    if recent.empty:
        return {"empty": True, "sales_timeline": []}

    ai = recent[recent["AI 추천 사용"].astype(bool)].copy()
    plain = recent[~recent["AI 추천 사용"].astype(bool)]
    member_by_id = members.set_index("customer_id") if not members.empty else pd.DataFrame()
    ai_member_ids = {int(value) for value in ai["customer_id"].dropna().tolist()}

    # 현재 데이터에는 '과거 등급' 스냅샷이 없으므로, 재방문·단골 지표는 AI 주문과 현재 등급을 함께 만족한 고객으로 본다.
    settled_new = {member_id for member_id in ai_member_ids if member_id in member_by_id.index
                   and member_by_id.at[member_id, "등급"] == "재방문"
                   and int(member_by_id.at[member_id, "방문 횟수"]) >= 2}
    growing_regulars = {member_id for member_id in ai_member_ids if member_id in member_by_id.index
                        and member_by_id.at[member_id, "등급"] == "단골"}

    ai_avg = int(ai["금액"].mean()) if len(ai) else None
    plain_avg = int(plain["금액"].mean()) if len(plain) else None

    settled_revenue = int(ai[ai["customer_id"].isin(settled_new)]["금액"].sum()) if settled_new else 0
    regular_revenue = int(ai[ai["customer_id"].isin(growing_regulars)]["금액"].sum()) if growing_regulars else 0
    # 최초 AI 추천 주문일을 도입 시점으로 보고 전·후의 '달력상 하루 평균 × 30일'을 월평균으로 환산한다.
    # 영업이 없던 날도 0원으로 포함해 특정 기간의 영업일 수가 결과를 부풀리지 않게 한다.
    timeline = orders.copy()
    timeline["일자"] = timeline["주문 시각"].dt.normalize()
    first_day, last_day = timeline["일자"].min(), timeline["일자"].max()
    daily_sales = timeline.groupby("일자")["금액"].sum().reindex(
        pd.date_range(first_day, last_day), fill_value=0).rename("매출").to_frame()
    all_ai = timeline[timeline["AI 추천 사용"].astype(bool)]
    adoption_date = all_ai["일자"].min() if len(all_ai) else None
    before = daily_sales[daily_sales.index < adoption_date] if adoption_date is not None else daily_sales.iloc[0:0]
    after = daily_sales[daily_sales.index >= adoption_date] if adoption_date is not None else daily_sales.iloc[0:0]
    baseline_monthly = round(float(before["매출"].mean()) * 30) if len(before) else None
    performance_monthly = round(float(after["매출"].mean()) * 30) if len(after) else None
    monthly_growth = (performance_monthly - baseline_monthly
                      if baseline_monthly is not None and performance_monthly is not None else None)
    growth_rate = monthly_growth / baseline_monthly if baseline_monthly and monthly_growth is not None else None
    post_orders = timeline[timeline["일자"] >= adoption_date] if adoption_date is not None else timeline.iloc[0:0]
    post_ai = post_orders[post_orders["AI 추천 사용"].astype(bool)]
    observed_ai_revenue = int(post_ai["금액"].sum())
    observed_post_revenue = int(post_orders["금액"].sum())
    post_days = len(after)
    ai_monthly_revenue = round(observed_ai_revenue / post_days * 30) if post_days else None
    sales_timeline = [{"date": day.strftime("%Y-%m-%d"), "revenue": int(row["매출"]),
                       "period": "AI 도입 이전" if adoption_date is not None and day < adoption_date else "AI 도입 이후"}
                      for day, row in daily_sales.iterrows()]

    return {
        "empty": False, "ai_orders": len(ai), "ai_customers": len(ai_member_ids),
        "ai_avg": ai_avg, "plain_avg": plain_avg,
        "observed_ai_revenue": observed_ai_revenue, "observed_post_revenue": observed_post_revenue,
        "ai_monthly_revenue": ai_monthly_revenue,
        "ai_revenue_share": observed_ai_revenue / observed_post_revenue if observed_post_revenue else 0,
        "settled_new": len(settled_new), "settled_revenue": settled_revenue,
        "growing_regulars": len(growing_regulars), "regular_revenue": regular_revenue,
        "sales_timeline": sales_timeline,
        "adoption_date": adoption_date.strftime("%Y-%m-%d") if adoption_date is not None else None,
        "pre_start": first_day.strftime("%Y-%m-%d"), "pre_days": len(before),
        "post_end": last_day.strftime("%Y-%m-%d"), "post_days": post_days,
        "baseline_monthly": baseline_monthly, "performance_monthly": performance_monthly,
        "monthly_growth": monthly_growth, "growth_rate": growth_rate,
    }


def _performance_charts(result: dict) -> None:
    """왼쪽은 도입 전후 추세, 오른쪽은 월평균 매출 위에 추가 매출을 빨간색으로 쌓아 보여 준다."""
    timeline = pd.DataFrame(result["sales_timeline"]).rename(columns={"date": "일자", "revenue": "매출", "period": "구간"})
    timeline["일자"] = pd.to_datetime(timeline["일자"])
    adoption = pd.Timestamp(result["adoption_date"]) if result["adoption_date"] else None
    baseline, performance = result["baseline_monthly"], result["performance_monthly"]
    if adoption is None or baseline is None or performance is None:
        st.info("AI 도입 전·후 월평균을 비교하려면 최초 AI 추천 주문일 이전의 매출 데이터가 필요합니다.")
        return

    # 도입 전·후 평균선은 일평균 값으로 표시하고, 빨간 세로선으로 최초 AI 주문일을 구분한다.
    averages = pd.DataFrame([
        {"일자": timeline["일자"].min(), "평균 매출": baseline / 30, "구간": "도입 전 평균"},
        {"일자": adoption - pd.Timedelta(days=1), "평균 매출": baseline / 30, "구간": "도입 전 평균"},
        {"일자": adoption, "평균 매출": performance / 30, "구간": "도입 후 평균"},
        {"일자": timeline["일자"].max(), "평균 매출": performance / 30, "구간": "도입 후 평균"},
    ])
    line = alt.Chart(timeline).mark_line(point=True, color="#f97316", strokeWidth=3).encode(
        x=alt.X("일자:T", title="주문일"), y=alt.Y("매출:Q", title="일 매출(원)"),
        tooltip=[alt.Tooltip("일자:T", title="주문일"), alt.Tooltip("매출:Q", title="매출", format=",")],
    )
    average_lines = alt.Chart(averages).mark_line(strokeDash=[6, 4], strokeWidth=2).encode(
        x="일자:T", y="평균 매출:Q", color=alt.Color(
            "구간:N", scale=alt.Scale(domain=["도입 전 평균", "도입 후 평균"], range=["#64748b", "#dc2626"]),
            legend=alt.Legend(title=None)), detail="구간:N")
    rule_data = pd.DataFrame({"일자": [adoption], "표시": [f"AI 마케팅 도입 {adoption:%Y-%m-%d}"]})
    rule = alt.Chart(rule_data).mark_rule(color="#dc2626", strokeWidth=2).encode(x="일자:T")
    rule_label = alt.Chart(rule_data).mark_text(color="#dc2626", align="left", dx=6,
                                                fontWeight="bold").encode(
        x="일자:T", y=alt.value(12), text="표시:N")

    added = max(0, result["monthly_growth"] or 0)
    bar_data = pd.DataFrame([
        {"비교": "기존 월평균", "구성": "기존 매출", "매출": baseline, "순서": 0},
        {"비교": "AI 도입 후", "구성": "기존 매출", "매출": min(baseline, performance), "순서": 0},
        {"비교": "AI 도입 후", "구성": "AI 마케팅 추가 매출", "매출": added, "순서": 1},
    ])
    bars = alt.Chart(bar_data).mark_bar(size=72).encode(
        x=alt.X("비교:N", title=None, sort=["기존 월평균", "AI 도입 후"]),
        y=alt.Y("sum(매출):Q", title="월환산 매출(원)"),
        color=alt.Color("구성:N", scale=alt.Scale(
            domain=["기존 매출", "AI 마케팅 추가 매출"], range=["#f59e0b", "#dc2626"]),
            legend=alt.Legend(title=None)),
        order=alt.Order("순서:Q", sort="ascending"),
        tooltip=["비교:N", "구성:N", alt.Tooltip("매출:Q", format=",")],
    )
    labels = alt.Chart(bar_data.groupby("비교", as_index=False)["매출"].sum()).mark_text(
        dy=-10, fontWeight="bold").encode(x=alt.X("비교:N", sort=["기존 월평균", "AI 도입 후"]),
                                            y="매출:Q", text=alt.Text("매출:Q", format=","))
    left, right = st.columns([3, 2], gap="large")
    left.subheader("AI 마케팅 도입 전·후 매출 추세")
    left.altair_chart((line + average_lines + rule + rule_label).properties(height=360), use_container_width=True)
    right.subheader("월평균 매출 증가")
    right.altair_chart((bars + labels).properties(height=360), use_container_width=True)


def _customer_section(members: pd.DataFrame) -> None:
    """고객 목록 화면과 같은 등급 자료와 고객 표를 보여 준다."""
    sec_title("2. 고객데이터", "고객 목록의 현재 등급과 방문 정보를 그대로 확인해요")
    counts = members["등급"].value_counts() if not members.empty else pd.Series(dtype=int)
    kpi_row(
        kpi("전체 고객", len(members), "명", accent=True),
        kpi("신규", int(counts.get("신규", 0)), "명"),
        kpi("재방문", int(counts.get("재방문", 0)), "명"),
        kpi("단골", int(counts.get("단골", 0)), "명"),
        kpi("휴면", int(counts.get("휴면", 0)), "명"),
        min_width=140,
    )
    st.dataframe(members, hide_index=True, width="stretch", height=320)


def _growth_section(result: dict) -> None:
    """AI 주문에서 직접 확인한 성과와 임시 산정 기준을 함께 표시한다."""
    sec_title("3. F&B그로스와 함께한 결과", "AI 추천 사용 주문을 기준으로 성과를 확인해요")
    if result["empty"]:
        st.info("주문 데이터가 쌓이면 고객 전환과 매출 성과가 표시됩니다.")
        return

    kpi_row(
        kpi("AI 추천 사용 주문", result["ai_orders"], "건", accent=True,
            sub=f"최근 30일 · 회원 고객 {result['ai_customers']}명"),
        kpi("AI 연동 월환산 매출", f"{result['ai_monthly_revenue']:,}" if result["ai_monthly_revenue"] is not None else "-",
            "원" if result["ai_monthly_revenue"] is not None else "",
            sub=f"실제 {result['post_days']}일간 AI 주문 {result['observed_ai_revenue']:,}원 × 30/{result['post_days']}" if result["post_days"] else "도입 후 데이터 필요"),
        kpi("AI 추천 주문 객단가", f"{result['ai_avg']:,}" if result["ai_avg"] is not None else "-",
            "원" if result["ai_avg"] is not None else "",
            sub=f"주문 1건 평균 · 일반 주문 {result['plain_avg']:,}원" if result["plain_avg"] is not None else "비교 주문 없음"),
        kpi("도입 후 AI 주문 매출 비중", f"{result['ai_revenue_share']:.1%}",
            sub=f"AI 주문 {result['observed_ai_revenue']:,}원 ÷ 도입 후 총매출 {result['observed_post_revenue']:,}원"),
        min_width=170,
    )
    kpi_row(
        kpi("2회 이상 방문한 신규고객", result["settled_new"], "명",
            sub=f"임시 기준: AI 주문 후 현재 재방문 · 연동 매출 {result['settled_revenue']:,}원"),
        kpi("새로 방문한 휴면고객", "-", "", sub="과거 등급 스냅샷 저장 후 정확히 집계 예정"),
        kpi("방문 횟수가 늘어난 단골 고객", result["growing_regulars"], "명",
            sub=f"임시 기준: AI 주문을 한 현재 단골 · 연동 매출 {result['regular_revenue']:,}원"),
        kpi("AI 추천 반응 고객", result["ai_customers"], "명", sub="AI 추천이 포함된 주문을 한 회원"),
        min_width=180,
    )
    monthly_growth = result["monthly_growth"]
    fee_rate = st.number_input("성과 수수료율(%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0,
                               help="최종 월환산 매출 차이 중 인보이스로 청구할 비율입니다.")
    invoice = max(0, monthly_growth or 0) * fee_rate / 100
    kpi_row(
        kpi("기존 월 평균 매출", f"{result['baseline_monthly']:,}" if result["baseline_monthly"] is not None else "-",
            "원" if result["baseline_monthly"] is not None else "",
            sub=f"도입 전 {result['pre_days']}일 실제 매출 ÷ {result['pre_days']}일 × 30" if result["pre_days"] else "도입 전 데이터 필요"),
        kpi("AI 도입 후 월환산 성과 매출", f"{result['performance_monthly']:,}" if result["performance_monthly"] is not None else "-",
            "원" if result["performance_monthly"] is not None else "",
            sub=f"도입 후 {result['post_days']}일 총매출 {result['observed_post_revenue']:,}원 ÷ {result['post_days']}일 × 30" if result["post_days"] else "도입 후 데이터 필요"),
        kpi("최종 월환산 매출 차이", f"{monthly_growth:,}" if monthly_growth is not None else "-",
            "원" if monthly_growth is not None else "",
            sub=(f"{result['performance_monthly']:,}원 − {result['baseline_monthly']:,}원 · {result['growth_rate']:+.1%}"
                 if result["growth_rate"] is not None else "비교 데이터 필요")),
        kpi("예상 인보이스", f"{invoice:,.0f}", "원", sub=f"월 추가 매출 × {fee_rate:g}%"),
        min_width=180,
    )
    st.caption("모든 월 수치는 같은 30일 환산 기준입니다. ‘AI 연동 월환산 매출’은 AI 표시 주문만, "
               "‘AI 도입 후 월환산 성과 매출’은 도입 후 발생한 전체 주문을 뜻합니다. 최종 매출 차이·빨간 막대·인보이스는 "
               "모두 ‘도입 후 월환산 총매출 − 기존 월평균 총매출’ 한 가지 값에 연결됩니다.")
    _performance_charts(result)


def page_growth_performance(repo) -> None:
    """기존 대시보드·고객 데이터와 AI 성과를 순서대로 조립한다."""
    page_head("F&B그로스 성과", "AI 추천을 통한 고객 전환과 매출 성장을 한눈에 확인하세요")
    # DB 연동 경로 1: backend/app/routers/admin/stats.py → backend/app/stores/stats.py
    # DB 테이블: orders, order_items, order_item_components, members, recommendation_events
    stats = repo.stats(st.session_state["grade_rule"])
    insights = repo.sales_insights(st.session_state["grade_rule"])
    # DB 연동 경로 2: backend/app/routers/admin/members.py → backend/app/stores/members.py → members 테이블
    members = repo.members(st.session_state["grade_rule"])
    # 성과 API: backend/app/routers/admin/opportunities.py → backend/app/services/growth_performance.py
    # DB 테이블: orders·order_items·order_item_components·members (API 모드에서는 화면 더미와 섞지 않음)
    result = repo.growth_performance(st.session_state["grade_rule"])
    render_sales_insights(stats, insights, title="1. 매출데이터",
                          subtitle="대시보드와 같은 매출 지표를 한곳에서 확인해요")
    _customer_section(members)
    _growth_section(result)

