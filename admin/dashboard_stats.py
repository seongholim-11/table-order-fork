"""대시보드용 추가 통계 - 주문·회원 표(DataFrame)만으로 계산해서 더미/서버 어느 쪽이든 똑같이 동작한다."""
from datetime import timedelta

import pandas as pd

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
GRADE_ORDER = ["신규", "재방문", "단골", "휴면"]
WINDOW_DAYS = 30


def recent_orders(orders: pd.DataFrame, days: int = WINDOW_DAYS) -> pd.DataFrame:
    """가장 최근 주문일 기준 최근 N일 주문 (오늘 주문이 없어도 화면이 비지 않게 최신 주문일을 기준으로 한다)."""
    if orders.empty:
        return orders
    last = orders["주문 시각"].max().normalize()
    return orders[orders["주문 시각"] >= last - timedelta(days=days - 1)]


def summarize(orders: pd.DataFrame, members: pd.DataFrame, tables: int | None = None) -> dict:
    df = recent_orders(orders)
    if df.empty:
        return {"empty": True}
    days = df["주문 시각"].dt.normalize().nunique()
    revenue = int(df["금액"].sum())
    hourly = df.groupby(df["주문 시각"].dt.hour)["금액"].sum()
    by_hour = {f"{h:02d}시": int(hourly.get(h, 0)) for h in range(int(hourly.index.min()), int(hourly.index.max()) + 1)}
    weekday = df.groupby(df["주문 시각"].dt.dayofweek)["금액"].sum()
    by_weekday = {WEEKDAYS[i]: int(weekday.get(i, 0)) for i in range(7)}
    per_table = df.groupby("테이블").size()
    used_tables = tables or int(per_table.size)
    last_day = df["주문 시각"].max().normalize()
    today_df = df[df["주문 시각"] >= last_day]
    grade = members.set_index("customer_id")["등급"] if not members.empty else pd.Series(dtype=str)
    buyers = df["customer_id"].dropna().unique()
    grades = pd.Series([grade.get(int(c)) for c in buyers if int(c) in grade.index]).value_counts()
    ai = df[df["AI 추천 사용"]]
    plain = df[~df["AI 추천 사용"]]
    return {
        "empty": False,
        "days": days,
        "revenue": revenue,
        "daily_revenue": revenue // days,
        "avg_ticket": revenue // len(df),
        "orders": len(df),
        "by_hour": by_hour,
        "peak_hour": max(by_hour, key=by_hour.get),
        "by_weekday": by_weekday,
        "peak_weekday": max(by_weekday, key=by_weekday.get),
        "turnover_today": round(len(today_df) / used_tables, 1),
        "turnover_avg": round(len(df) / days / used_tables, 1),
        "tables": used_tables,
        # 사장님이 지금 붐비는 테이블을 볼 수 있도록 최근 30일 누적이 아닌 마지막 영업일 주문만 센다.
        "top_tables": {f"{int(t)}번": int(n) for t, n in today_df.groupby("테이블").size().sort_values(ascending=False).head(5).items()},
        "customer_grades": {g: int(grades.get(g, 0)) for g in GRADE_ORDER},
        "returning_share": (sum(int(grades.get(g, 0)) for g in ("재방문", "단골")) / grades.sum()) if grades.sum() else None,
        "ai_avg_ticket": int(ai["금액"].mean()) if len(ai) else None,
        "plain_avg_ticket": int(plain["금액"].mean()) if len(plain) else None,
        "ai_share": len(ai) / len(df),
        **_trend_stats(orders, df),
    }


TICKET_BANDS = [("2만원 미만", 0, 20_000), ("2~4만원", 20_000, 40_000), ("4~6만원", 40_000, 60_000),
                ("6~8만원", 60_000, 80_000), ("8만원 이상", 80_000, None)]


def _change(now: int, before: int) -> float | None:
    """증감률 (비교 대상이 0이면 None)."""
    return (now - before) / before if before else None


def _trend_stats(all_orders: pd.DataFrame, df: pd.DataFrame) -> dict:
    """추이·비교·회원/비회원·주문 금액대·단골 고객 (최근 30일 df 기준, 주차 비교는 전체 주문에서 계산)."""
    day = df["주문 시각"].dt.normalize()
    daily = df.groupby(day)["금액"].sum()
    last = day.max()
    by_day = {d.strftime("%m/%d"): int(daily.get(d, 0)) for d in pd.date_range(last - timedelta(days=13), last)}
    all_day = all_orders["주문 시각"].dt.normalize()
    all_daily = all_orders.groupby(all_day)["금액"].sum()

    def span(start, days):
        return int(all_daily[(all_daily.index >= start) & (all_daily.index < start + timedelta(days=days))].sum())

    this_week, prev_week = span(last - timedelta(days=6), 7), span(last - timedelta(days=13), 7)
    last_day_rev, same_weekday_rev = int(all_daily.get(last, 0)), int(all_daily.get(last - timedelta(days=7), 0))
    member = df[df["customer_id"].notna()]
    guest = df[df["customer_id"].isna()]
    today = df[df["주문 시각"].dt.normalize() == last]
    today_member_orders = today[today["customer_id"].notna()]
    today_guest_orders = today[today["customer_id"].isna()]
    today_member_revenue = int(today_member_orders["금액"].sum())
    today_guest_revenue = int(today_guest_orders["금액"].sum())
    # 서비스가 필요한 손님을 바로 찾을 수 있도록 회원은 고객별, 신원을 모르는 비회원은 테이블별로 합친다.
    today_member = today[today["customer_id"].notna()].sort_values("주문 시각")
    member_spend = today_member.groupby("customer_id").agg(
        닉네임=("닉네임", "first"), 금액=("금액", "sum"), 횟수=("금액", "size"), 테이블=("테이블", "last"))
    member_rows = [{"name": row["닉네임"], "amount": int(row["금액"]), "orders": int(row["횟수"]),
                    "table": int(row["테이블"]), "kind": "회원"} for _, row in member_spend.iterrows()]
    guest_spend = today[today["customer_id"].isna()].groupby("테이블").agg(금액=("금액", "sum"), 횟수=("금액", "size"))
    guest_rows = [{"name": "비회원", "amount": int(row["금액"]), "orders": int(row["횟수"]),
                   "table": int(table), "kind": "비회원"} for table, row in guest_spend.iterrows()]
    top_customers = sorted(member_rows + guest_rows, key=lambda row: row["amount"], reverse=True)[:5]
    bands = {name: int(((df["금액"] >= lo) & ((df["금액"] < hi) if hi else True)).sum()) for name, lo, hi in TICKET_BANDS}
    return {
        "by_day": by_day,
        "last_day": last.strftime("%m/%d"),
        "week_revenue": this_week, "week_change": _change(this_week, prev_week),
        "last_day_revenue": last_day_rev, "last_day_change": _change(last_day_rev, same_weekday_rev),
        "member_order_share": len(member) / len(df),
        # 오늘 전체 매출은 회원 매출과 비회원 매출의 합이며, 화면의 비중은 주문 건수가 아닌 금액으로 계산한다.
        "member_revenue_share": today_member_revenue / last_day_rev if last_day_rev else None,
        "member_revenue": today_member_revenue,
        "guest_revenue": today_guest_revenue,
        "member_avg_ticket": int(member["금액"].mean()) if len(member) else None,
        "guest_avg_ticket": int(guest["금액"].mean()) if len(guest) else None,
        "ticket_bands": bands,
        "top_customers": top_customers,
        "top_customer_share": (sum(row["amount"] for row in top_customers) / today["금액"].sum()
                               if top_customers and today["금액"].sum() else None),
    }


def customer_care(members: pd.DataFrame) -> dict:
    """고객 관리 지표: 전체 회원, 휴면, 마케팅 수신 동의·거부."""
    total = len(members)
    if not total:
        return {"total": 0}
    return {
        "total": total,
        "dormant": int((members["등급"] == "휴면").sum()),
        "consent": int((members["마케팅 수신 동의"] & ~members["수신거부"]).sum()),
        "opted_out": int(members["수신거부"].sum()),
    }


def menu_alerts(menus: pd.DataFrame, popular: list[dict]) -> dict:
    """품절 메뉴와, 인기 메뉴 TOP 중 품절된 메뉴 (놓치고 있는 매출 신호)."""
    sold_out = menus[~menus["판매 여부"].astype(bool)]["메뉴명"].tolist()
    return {"sold_out": sold_out, "popular_sold_out": [m["name"] for m in popular if m["name"] in sold_out]}
