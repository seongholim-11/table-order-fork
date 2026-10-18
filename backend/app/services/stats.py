"""DB에서 읽은 주문·회원으로 대시보드 기본 통계를 계산한다."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from app.services.grades import AGE_GROUPS, KST, age_group, gender_label, grade_of


def order_date(value: str) -> date:
    """시간대 없는 SQLite 시각도 UTC로 해석해 한국 날짜를 구한다."""
    return order_time(value).date()


def order_time(value: str) -> datetime:
    """시간대 표기가 섞인 DB 시각을 한국 시간으로 통일해 날짜·시간 집계를 맞춘다."""
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(KST)


def dashboard(orders: list[dict], members: list[dict], recommendations: int, today: date, rule: dict) -> dict:
    """오늘 지표와 전체 기록 지표를 기존 화면의 응답 모양으로 돌려준다."""
    todays = [order for order in orders if order_date(order["ts"]) == today]
    # 같은 회원이 여러 번 주문해도 고객 수는 한 명으로 센다. 비회원은 분류하지 않는다.
    customer_ids = {order["member_id"] for order in todays if order.get("member_id") is not None}
    grades = Counter(grade_of(member, today, **rule) for member in members if member["id"] in customer_ids)
    ages = Counter(age_group(member.get("birth_year"), today) for member in members)
    genders = Counter(gender_label(member.get("gender")) for member in members)
    popularity = Counter()
    for order in orders:
        for line in order.get("lines", []):
            # 조합 두 세트에 메뉴가 두 개씩 있으면 해당 메뉴 수량은 네 개다.
            if line.get("kind") == "combo" or str(line.get("id", "")).startswith("combo:"):
                for component in line.get("components", []):
                    popularity[component["name"]] += component["qty"] * line["qty"]
            else:
                popularity[line["name"]] += line["qty"]
    ai_orders = sum(bool(order.get("ai_combo")) for order in orders)
    return {
        "today_orders": len(todays),
        "avg_order_amount": sum(order["total"] for order in todays) // len(todays) if todays else 0,
        "new_customers": grades["신규"],
        "returning_customers": grades["재방문"] + grades["단골"],
        "age_groups": {group: ages[group] for group in AGE_GROUPS},
        "genders": {gender: genders[gender] for gender in ("여", "남") if genders[gender]},
        "popular_menus": [{"name": name, "qty": qty} for name, qty in
                          sorted(popularity.items(), key=lambda item: (-item[1], item[0]))[:10]],
        "ai": {"recommendations": recommendations, "ai_orders": ai_orders,
               "hit_rate": ai_orders / recommendations if recommendations else None,
               "definition": "전체 AI 조합이 포함된 주문 수 / 전체 추천 노출 횟수 (임시 기준)"},
    }


# 화면의 summarize·_trend_stats를 서버의 일반 파이썬 자료형에 맞게 이식했다.
# 화면 원본은 서버 없이 실행하는 더미 모드와 결과 비교 테스트용으로 유지한다.
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
GRADE_ORDER = ("신규", "재방문", "단골", "휴면")
TICKET_BANDS = (("2만원 미만", 0, 20000), ("2~4만원", 20000, 40000), ("4~6만원", 40000, 60000),
                ("6~8만원", 60000, 80000), ("8만원 이상", 80000, None))


def _change(current: int, previous: int) -> float | None:
    """비교 기간의 매출이 0원이면 증감률을 계산할 수 없으므로 null로 보낸다."""
    return (current - previous) / previous if previous else None


def _average(orders: list[dict]) -> int | None:
    """주문이 없는 집단의 객단가는 0원과 구분해 표시한다."""
    return sum(order["total"] for order in orders) // len(orders) if orders else None


def sales_insights(orders: list[dict], members: list[dict], tables: int, today: date, rule: dict) -> dict:
    """가장 최근 주문일 기준 30일 통계와 실제 오늘 매출을 계산한다."""
    if not orders:
        return {"empty": True}
    # 문자열 정렬은 UTC/KST·공백/T가 섞이면 틀리므로 변환한 시각으로 기간을 정한다.
    normalized = [{**order, "at": order_time(order["ts"])} for order in orders]
    last = max(order["at"].date() for order in normalized)
    first = last - timedelta(days=29)
    recent = [order for order in normalized if order["at"].date() >= first]
    days = len({order["at"].date() for order in recent})
    revenue = sum(order["total"] for order in recent)
    hourly, weekday = Counter(), Counter()
    for order in recent:
        hourly[order["at"].hour] += order["total"]
        weekday[order["at"].weekday()] += order["total"]
    by_hour = {f"{hour:02d}시": hourly[hour] for hour in range(min(hourly), max(hourly) + 1)}
    by_weekday = {name: weekday[index] for index, name in enumerate(WEEKDAYS)}
    latest_orders = [order for order in recent if order["at"].date() == last]
    table_counts = Counter(order["table_no"] for order in latest_orders)
    # 잘못된 테이블 수가 설정돼도 나눗셈 오류를 내지 않고 실제 사용 테이블 수로 계산한다.
    used_tables = tables if tables > 0 else len({order["table_no"] for order in recent})
    buyers = {order["member_id"] for order in recent if order["member_id"] is not None}
    grades = Counter(grade_of(member, today, **rule) for member in members if member["id"] in buyers)
    ai = [order for order in recent if order["ai_combo"]]
    plain = [order for order in recent if not order["ai_combo"]]
    return {
        "empty": False, "days": days, "revenue": revenue, "daily_revenue": revenue // days,
        "avg_ticket": revenue // len(recent), "orders": len(recent),
        # 시연 화면은 실제 오늘 날짜가 지나도 마지막 주문일의 건수와 매출을 함께 표시한다.
        "last_day_orders": len(latest_orders),
        "today_revenue": sum(order["total"] for order in normalized if order["at"].date() == today),
        "by_hour": by_hour, "peak_hour": max(by_hour, key=by_hour.get),
        "by_weekday": by_weekday, "peak_weekday": max(by_weekday, key=by_weekday.get),
        "turnover_today": round(len(latest_orders) / used_tables, 1),
        "turnover_avg": round(len(recent) / days / used_tables, 1), "tables": used_tables,
        # 동률이면 테이블 번호가 작은 순서로 고정해 새로고침 때 순위가 흔들리지 않게 한다.
        "top_tables": {f"{table}번": count for table, count in
                       sorted(table_counts.items(), key=lambda item: (-item[1], item[0]))[:5]},
        "customer_grades": {grade: grades[grade] for grade in GRADE_ORDER},
        "returning_share": (grades["재방문"] + grades["단골"]) / sum(grades.values()) if grades else None,
        "ai_avg_ticket": _average(ai), "plain_avg_ticket": _average(plain), "ai_share": len(ai) / len(recent),
        **_sales_trends(normalized, recent, latest_orders, last),
    }


def _sales_trends(all_orders: list[dict], recent: list[dict], latest_orders: list[dict], last: date) -> dict:
    """14일 매출·전주 비교·금액대·고객별 매출을 같은 기간에서 계산한다."""
    daily = Counter()
    for order in all_orders:
        daily[order["at"].date()] += order["total"]

    def span(start: date, days: int) -> int:
        return sum(daily[start + timedelta(days=offset)] for offset in range(days))

    this_week, previous_week = span(last - timedelta(days=6), 7), span(last - timedelta(days=13), 7)
    member_orders = [order for order in recent if order["member_id"] is not None]
    guest_orders = [order for order in recent if order["member_id"] is None]
    member_revenue = sum(order["total"] for order in latest_orders if order["member_id"] is not None)
    guest_revenue = daily[last] - member_revenue
    # 회원은 ID별, 비회원은 테이블별로 합산한다. 테이블은 마지막 주문 위치로 보여 준다.
    customers = {}
    for order in sorted(latest_orders, key=lambda order: (order["at"], order["id"])):
        is_member = order["member_id"] is not None
        key = ("회원", order["member_id"]) if is_member else ("비회원", order["table_no"])
        customer = customers.setdefault(key, {"name": (order.get("nickname") or "비회원") if is_member else "비회원",
                                              "amount": 0, "orders": 0, "table": order["table_no"], "kind": key[0]})
        customer["amount"] += order["total"]
        customer["orders"] += 1
        customer["table"] = order["table_no"]
    # 동액이면 화면 원본처럼 회원 ID, 비회원 테이블 번호 순서를 따른다.
    top_customers = sorted((customers[key] for key in sorted(customers, key=lambda key: (key[0] != "회원", key[1]))),
                           key=lambda customer: -customer["amount"])[:5]
    return {
        "by_day": {(last - timedelta(days=offset)).strftime("%m/%d"): daily[last - timedelta(days=offset)]
                   for offset in range(13, -1, -1)},
        "last_day": last.strftime("%m/%d"), "last_order_date": last.isoformat(),
        "week_revenue": this_week, "week_change": _change(this_week, previous_week),
        "last_day_revenue": daily[last], "last_day_change": _change(daily[last], daily[last - timedelta(days=7)]),
        "member_order_share": len(member_orders) / len(recent),
        "member_revenue_share": member_revenue / daily[last] if daily[last] else None,
        "member_revenue": member_revenue, "guest_revenue": guest_revenue,
        "member_avg_ticket": _average(member_orders), "guest_avg_ticket": _average(guest_orders),
        "ticket_bands": {name: sum(order["total"] >= lower and (upper is None or order["total"] < upper)
                                   for order in recent) for name, lower, upper in TICKET_BANDS},
        "top_customers": top_customers,
        "top_customer_share": sum(customer["amount"] for customer in top_customers) / daily[last]
                              if top_customers and daily[last] else None,
    }


def menu_stock_alerts(menus: list[dict], sales: list[dict]) -> list[dict]:
    """현재 품절 메뉴와 전체 판매 수량 TOP10에 드는 품절 메뉴를 구분한다."""
    by_id = {menu["id"]: menu for menu in menus}
    by_name = {}
    for menu in menus:
        by_name.setdefault(menu["name"], []).append(menu["id"])
    quantities = Counter()
    for sale in sales:
        menu_id = sale["menu_id"]
        if menu_id is None:
            # 예전 주문의 ID가 없으면 이름이 유일할 때만 연결해 동명 메뉴를 잘못 집계하지 않는다.
            matches = by_name.get(sale["name"], [])
            menu_id = matches[0] if len(matches) == 1 else None
        if menu_id in by_id:
            # ID가 있으면 이름이 바뀌어도 같은 메뉴로 집계한다.
            quantities[menu_id] += sale["qty"]
    popular = set(sorted(quantities, key=lambda menu_id: (-quantities[menu_id], by_id[menu_id]["name"], menu_id))[:10])
    return [{"kind": "soldout", "menu_id": menu["id"], "name": menu["name"], "title": "품절 메뉴",
             "detail": f"{menu['name']} 메뉴가 현재 품절이에요.", "popular": menu["id"] in popular}
            for menu in menus if menu["is_soldout"]]
