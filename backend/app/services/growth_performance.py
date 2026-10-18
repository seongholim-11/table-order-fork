"""F&B그로스 성과: orders·members DB 자료를 동일한 30일 기준으로 비교한다."""

from datetime import date, timedelta
from collections import Counter

from app.services.grades import grade_of
from app.services.stats import order_date


# DB 연동: backend/app/stores/stats.py가 orders·order_items·order_item_components를 읽고,
# backend/app/stores/members.py가 members를 읽어 아래 함수에 전달한다. 화면 더미 데이터는 이 경로에 들어오지 않는다.
def calculate(orders: list[dict], members: list[dict], today: date, rule: dict) -> dict:
    """최초 AI 주문일 전후의 월환산 매출과 고객 성과를 계산한다."""
    if not orders:
        return {"empty": True, "sales_timeline": []}
    rows = [{"date": order_date(order["ts"]), "amount": int(order["total"]),
             "ai": bool(order.get("ai_combo")), "member_id": order.get("member_id")} for order in orders]
    first, last = min(row["date"] for row in rows), max(row["date"] for row in rows)
    adoption = min((row["date"] for row in rows if row["ai"]), default=None)
    daily = Counter({first + timedelta(days=offset): 0 for offset in range((last - first).days + 1)})
    for row in rows:
        daily[row["date"]] += row["amount"]
    before_days = [day for day in daily if adoption and day < adoption]
    after_days = [day for day in daily if adoption and day >= adoption]
    baseline = round(sum(daily[day] for day in before_days) / len(before_days) * 30) if before_days else None
    performance = round(sum(daily[day] for day in after_days) / len(after_days) * 30) if after_days else None
    difference = performance - baseline if baseline is not None and performance is not None else None

    recent_start = last - timedelta(days=29)
    recent = [row for row in rows if row["date"] >= recent_start]
    recent_ai = [row for row in recent if row["ai"]]
    recent_plain = [row for row in recent if not row["ai"]]
    post = [row for row in rows if adoption and row["date"] >= adoption]
    post_ai = [row for row in post if row["ai"]]
    observed_ai = sum(row["amount"] for row in post_ai)
    observed_post = sum(row["amount"] for row in post)
    ai_monthly = round(observed_ai / len(after_days) * 30) if after_days else None

    member_by_id = {member["id"]: member for member in members}
    ai_member_ids = {row["member_id"] for row in recent_ai if row["member_id"] is not None}
    settled = {member_id for member_id in ai_member_ids if member_id in member_by_id
               and grade_of(member_by_id[member_id], today, **rule) == "재방문"
               and int(member_by_id[member_id].get("visit_count") or 0) >= 2}
    regulars = {member_id for member_id in ai_member_ids if member_id in member_by_id
                and grade_of(member_by_id[member_id], today, **rule) == "단골"}
    revenue_for = lambda ids: sum(row["amount"] for row in recent_ai if row["member_id"] in ids)
    return {
        "empty": False, "ai_orders": len(recent_ai), "ai_customers": len(ai_member_ids),
        "ai_avg": round(sum(row["amount"] for row in recent_ai) / len(recent_ai)) if recent_ai else None,
        "plain_avg": round(sum(row["amount"] for row in recent_plain) / len(recent_plain)) if recent_plain else None,
        "observed_ai_revenue": observed_ai, "observed_post_revenue": observed_post,
        "ai_monthly_revenue": ai_monthly,
        "ai_revenue_share": observed_ai / observed_post if observed_post else 0,
        "settled_new": len(settled), "settled_revenue": revenue_for(settled),
        "growing_regulars": len(regulars), "regular_revenue": revenue_for(regulars),
        "sales_timeline": [{"date": day.isoformat(), "revenue": daily[day],
                            "period": "AI 도입 이전" if adoption and day < adoption else "AI 도입 이후"}
                           for day in sorted(daily)],
        "adoption_date": adoption.isoformat() if adoption else None,
        "pre_start": first.isoformat(), "pre_days": len(before_days),
        "post_end": last.isoformat(), "post_days": len(after_days),
        "baseline_monthly": baseline, "performance_monthly": performance,
        "monthly_growth": difference,
        "growth_rate": difference / baseline if baseline and difference is not None else None,
    }
