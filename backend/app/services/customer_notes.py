"""오늘 주문한 단골의 방문 기록과 확인 가능한 메뉴 취향을 사장님에게 알린다."""

from collections import Counter, defaultdict
from datetime import date, timedelta

from app.services.stats import order_time
from app.services.grades import grade_of


# 주류·음료가 섞인 사이드 분류는 제외하고, 안주로 확인된 분류만 사용한다.
FOOD_CATEGORIES = {"chicken", "anju", "soup", "dry"}
MIN_HISTORY_DAYS = 5
MIN_PREFERENCE_PERCENT = 80


def _visit_greeting(member: dict, history: dict, today: date, delivery: str,
                    regular_visits: int) -> tuple[str, str]:
    """방문 감사는 메뉴 선호율과 무관하게, 확인된 방문·주문 상황으로 고른다."""
    gap = (today - max(history)).days if history else None
    varied = len(history) >= 3 and len(set().union(*history.values())) >= 3
    detail = ""
    if gap is not None and gap >= 14:
        detail = f" 이전 주문은 {gap}일 전입니다."
        suggestions = (
            "다시 뵈니 반갑습니다. 또 찾아주셔서 감사해요! 오늘도 편하게 즐기다 가세요.",
            f"다시 찾아주셔서 반갑습니다! 주문하신 {delivery} 맛있게 드세요.",
            "또 뵙게 되어 기쁩니다. 오늘도 즐거운 시간 보내세요!",
        )
    elif varied:
        detail = " 이전 주문에서 여러 안주를 고르신 기록이 있습니다."
        suggestions = (
            f"또 찾아주셔서 감사합니다! 오늘 고르신 {delivery}도 맛있게 즐겨 주세요.",
            f"다시 뵈니 반갑습니다. {delivery} 준비해 드렸어요. 드셔 보시고 편하게 말씀해 주세요!",
            "자주 찾아주셔서 감사해요. 오늘도 입맛에 맞게 즐기셨으면 좋겠습니다!",
        )
    elif member["visit_count"] == regular_visits:
        suggestions = (
            "벌써 여러 번 찾아주셨네요. 계속 찾아주셔서 감사합니다! 오늘도 편하게 즐기세요.",
            f"또 찾아주셔서 감사합니다. 오늘 주문하신 {delivery}도 맛있게 드세요!",
            "다시 뵈어 반갑습니다. 자주 찾아주셔서 감사합니다. 오늘도 맛있게 드세요!",
        )
    elif member["visit_count"] >= 10:
        suggestions = (
            "늘 찾아주셔서 감사합니다. 오늘도 편안하고 즐거운 시간 보내세요!",
            f"자주 뵈니 반갑습니다! 오늘 주문하신 {delivery}도 맛있게 드세요.",
            "꾸준히 찾아주셔서 감사해요. 필요한 것이 있으면 언제든 편하게 말씀해 주세요!",
        )
    else:
        suggestions = (
            "다시 찾아주셔서 감사합니다. 오늘도 편하게 즐기다 가세요!",
            f"또 뵈니 반갑습니다! 오늘 주문하신 {delivery}도 맛있게 드세요.",
            "자주 찾아주셔서 감사해요. 드시다가 필요한 것 있으면 편하게 말씀해 주세요!",
        )
    return detail, suggestions[member["id"] % len(suggestions)]


def _is_birthday(member: dict, today: date) -> bool:
    """카카오가 주는 MMDD 생일이 오늘인지 확인한다."""
    digits = "".join(ch for ch in str(member.get("birthday") or "") if ch.isdigit())[-4:]
    return digits == today.strftime("%m%d")


def _visit_label(day: date, table_no: int, menus: list[str]) -> str:
    menu_text = ", ".join(menus) if menus else "주문 메뉴 확인 전"
    return f"{day.month}월 {day.day}일 {table_no}번 테이블에서 {menu_text}을(를) 주문"


def regular_notes(members: list[dict], orders: list[dict], lines: list[dict],
                  menus: list[dict], today: date, dormant_days: int = 30, repeat_visits: int = 2,
                  regular_visits: int = 5, weather_text: str = "", visits: list[dict] | None = None) -> list[dict]:
    """단골·주간 반복 방문·생일·첫 방문 기념일이 확인된 손님에게만 응대를 제안한다."""
    by_id = {menu["id"]: menu for menu in menus}
    by_name = defaultdict(list)
    for menu in menus:
        by_name[menu["name"]].append(menu["id"])
    by_order = {order["id"]: {**order, "at": order_time(order["ts"])} for order in orders}
    foods, ordered_menus = defaultdict(set), defaultdict(set)
    for line in lines:
        if line["qty"] <= 0 or line["order_id"] not in by_order:
            continue
        menu_id = line["menu_id"]
        if menu_id is None:
            # ID 없는 옛 주문은 이름이 유일할 때만 연결해 다른 메뉴의 취향으로 오해하지 않는다.
            matches = by_name[line["name"]]
            menu_id = matches[0] if len(matches) == 1 else None
        menu = by_id.get(menu_id)
        if menu:
            # 단골 안내는 음료 주문도 포함하지만, 선호 안주는 안주 분류로만 계산한다.
            ordered_menus[line["order_id"]].add(menu_id)
            if menu["category_id"] in FOOD_CATEGORIES:
                foods[line["order_id"]].add(menu_id)

    by_member = defaultdict(list)
    for order in by_order.values():
        if order["member_id"] is not None and order["at"].date() <= today:
            by_member[order["member_id"]].append(order)
    # 방문 횟수의 원본은 로그인 기록이다. 옛 데이터에 로그인 행이 없을 수 있어 주문일도 보조 근거로 합친다.
    login_days = defaultdict(set)
    for visit in visits or []:
        raw_day = visit.get("login_day")
        if raw_day:
            login_days[visit["member_id"]].add(date.fromisoformat(str(raw_day)[:10]))

    result = []
    for member in members:
        # 고객 등급과 특별 상황은 계산하되, 일반 재방문만으로는 제안을 만들지 않는다.
        grade = grade_of(member, today, repeat=repeat_visits, regular=regular_visits, dormant=dormant_days)
        history, history_all, history_orders, current = defaultdict(set), defaultdict(set), [], []
        for order in by_member[member["id"]]:
            day = order["at"].date()
            if day < today:
                # 같은 날 추가 주문을 여러 번 하거나 수량이 많아도 주문일은 한 번만 센다.
                history[day].update(foods[order["id"]])
                history_all[day].update(ordered_menus[order["id"]])
                history_orders.append(order)
            else:
                current.append(order)
        # 방문 횟수만으로도 단골을 안내한다. 80%는 메뉴 취향을 추가할 때만 적용한다.
        favorite, frequency, rate = None, 0, None
        if len(history) >= MIN_HISTORY_DAYS:
            counts = Counter(menu_id for daily in history.values() for menu_id in daily)
            if counts:
                candidate = min(counts, key=lambda menu_id: (-counts[menu_id], by_id[menu_id]["name"], menu_id))
                if counts[candidate] * 100 >= len(history) * MIN_PREFERENCE_PERCENT:
                    favorite, frequency = candidate, counts[candidate]
                    rate = frequency / len(history)
        # 실제 오늘 주문에 있는 메뉴만 전달 대상으로 안내하고, 무료 서비스만 있으면 제외한다.
        paid_orders = [order for order in current if ordered_menus[order["id"]]]
        if not paid_orders:
            continue
        distinct_visit_days = login_days[member["id"]] | {order["at"].date() for order in history_orders + current}
        weekly_visits = sum(day >= today - timedelta(days=6) for day in distinct_visit_days)
        first_visit = min(distinct_visit_days) if distinct_visit_days else None
        anniversary = bool(first_visit and first_visit.year < today.year
                           and (first_visit.month, first_visit.day) == (today.month, today.day))
        birthday = _is_birthday(member, today)
        if grade == "휴면" or (grade != "단골" and weekly_visits < 2 and not birthday and not anniversary):
            continue
        latest = max(paid_orders, key=lambda order: (order["at"], order["id"]))
        current_menus = set().union(*(ordered_menus[order["id"]] for order in current
                                     if order["table_no"] == latest["table_no"]))
        latest_menus = foods[latest["id"]] or ordered_menus[latest["id"]]
        delivery_id = favorite if favorite in latest_menus else min(latest_menus, key=lambda menu_id: (by_id[menu_id]["name"], menu_id))
        delivery = by_id[delivery_id]["name"]
        today_menus = sorted(by_id[menu_id]["name"] for menu_id in current_menus)
        name = by_id[favorite]["name"] if favorite else None
        changed_today = favorite not in current_menus if favorite else None
        context = (f"로그인 기록 기준 {member['visit_count']}번째 방문인 {grade} 고객입니다. "
                   f"오늘 주문: {', '.join(today_menus)}. 현재 {latest['table_no']}번 테이블입니다.")
        # 기본 방문 인사에는 취향 비율을 섞지 않고, 선택 안내에만 메뉴 선호 근거를 둔다.
        visit_detail, visit_note = _visit_greeting(member, history, today, delivery, regular_visits)
        visit_context = context + visit_detail

        previous = max(history_orders, key=lambda order: (order["at"], order["id"])) if history_orders else None
        previous_menus = (sorted(by_id[menu_id]["name"] for menu_id in history_all[previous["at"].date()])
                          if previous else [])
        previous_visit = (_visit_label(previous["at"].date(), previous["table_no"], previous_menus)
                          if previous else "이전 주문 기록 없음")
        age = today.year - member["birth_year"] if birthday and member.get("birth_year") else None

        # 80% 기준이 아직 안 쌓였어도 가장 자주 확인된 과거 메뉴는 서비스 아이디어로만 사용한다.
        past_counts = Counter(menu_id for daily in history_all.values() for menu_id in daily)
        most_ordered_id = (min(past_counts, key=lambda menu_id: (-past_counts[menu_id], by_id[menu_id]["name"], menu_id))
                           if past_counts else None)
        most_ordered = by_id[most_ordered_id]["name"] if most_ordered_id else None
        rainy_favorite = bool(most_ordered and "파전" in most_ordered and
                              any(word in weather_text for word in ("비", "소나기", "천둥")))
        if birthday:
            age_text = f" 만 {age}세" if age is not None else ""
            care_reason = f"오늘은 {member['nickname']}님의{age_text} 생일이고, {member['visit_count']}번째 방문입니다."
            service_suggestion = f"생일 축하 서비스와 함께 {most_ordered or '자주 드시는 메뉴'} 취향을 기억하고 있다고 알려 주세요."
            visit_note = (f"{member['nickname']}님, 생일 축하드립니다! 자주 드시던 "
                          f"{most_ordered + '도 기억하고 있어요. ' if most_ordered else ''}오늘 작은 생일 서비스를 준비해 드릴게요.")
            special_event = "birthday"
        elif anniversary:
            care_reason = f"오늘은 첫 방문일로부터 {today.year - first_visit.year}주년입니다. 다시 찾아주신 기념일을 알아봐 주세요."
            service_suggestion = f"첫 방문 기념 인사와 함께 {most_ordered or delivery} 취향에 맞는 작은 서비스를 제안해 보세요."
            visit_note = f"{member['nickname']}님, 처음 찾아주신 날부터 함께해 주셔서 감사합니다. 작은 기념 서비스를 준비했어요."
            special_event = "visit_anniversary"
        elif rainy_favorite:
            care_reason = f"오늘은 {weather_text}이고, {member['nickname']}님은 이전에 {most_ordered}을(를) 자주 주문했습니다."
            service_suggestion = f"비 오는 날 취향에 맞춰 {most_ordered} 또는 작은 곁들임 서비스를 제안해 보세요."
            visit_note = f"{member['nickname']}님, 비 오는 날 좋아하시던 {most_ordered} 생각나서 작은 서비스를 준비했어요."
            special_event = "rainy_favorite"
        elif weekly_visits >= 2:
            care_reason = f"최근 7일 동안 {weekly_visits}일 방문한 고객입니다. 자주 찾아주는 사실을 지금 알아봐 주면 충성 고객 전환에 도움이 됩니다."
            service_suggestion = f"자주 드신 {most_ordered or delivery}와 어울리는 작은 서비스 메뉴를 드려 보세요."
            visit_note = (f"{member['nickname']}님, 이번 주에 자주 찾아주셔서 정말 감사합니다. "
                          f"오늘 고르신 {delivery}와 함께 작은 서비스를 준비했어요.")
            special_event = "frequent_week"
        else:
            care_reason = f"{member['visit_count']}회 방문한 단골 고객입니다. 오늘 주문을 계기로 감사 인사를 전해 보세요."
            service_suggestion = f"단골 고객에게 {most_ordered or delivery}와 어울리는 작은 감사 서비스를 제안해 보세요."
            special_event = "regular_customer"
        if favorite:
            context += f" 이전 주문일 {len(history)}일 중 {frequency}일에 {name} 메뉴를 주문했습니다(80% 이상)."
            if changed_today:
                context += f" 오늘 확인된 주문에는 {name} 메뉴가 없습니다."
            else:
                context += f" 오늘도 {name} 주문이 확인됐습니다."
            if by_id[favorite]["is_soldout"]:
                # 현재 품절 사실만 알리고, 손님이 다른 메뉴를 고른 이유는 추측하지 않는다.
                context += f" 참고로 {name} 메뉴는 현재 품절입니다."
        if favorite and delivery_id == favorite:
            suggestions = (
                f"오늘도 {name} 골라 주셨네요. 늘 찾아주셔서 감사합니다!",
                f"다시 뵈니 반갑습니다. 즐겨 드시는 {name}, 오늘도 맛있게 드세요!",
                f"자주 찾아주셔서 감사해요. 오늘도 {name} 맛있게 즐겨 주세요!",
            )
        elif favorite and changed_today and not by_id[favorite]["is_soldout"]:
            suggestions = (
                f"평소 {name} 자주 드셨는데, 오늘은 {delivery} 골라 주셨네요. 이것도 맛있게 드세요!",
                f"또 뵈니 반갑습니다! 오늘 고르신 {delivery}도 입맛에 맞으셨으면 좋겠어요.",
                f"늘 찾아주셔서 감사합니다. 오늘은 {delivery} 즐겨 보시고 어떠셨는지 편하게 말씀해 주세요!",
            )
        else:
            suggestions = (visit_note,)
        # 같은 손님에게 새로고침마다 말이 바뀌지 않도록 고르되, 문구 선택은 사장님에게 맡긴다.
        note = suggestions[member["id"] % len(suggestions)]
        result.append({
            "member_id": member["id"], "nickname": member["nickname"], "visit_count": member["visit_count"],
            "favorite_menu": name, "history_days": len(history), "favorite_days": frequency,
            "preference_rate": rate, "changed_today": changed_today, "context": context,
            "today_table": latest["table_no"], "today_menus": today_menus,
            "delivery_menu": delivery, "current_order_id": latest["id"], "note": note,
            "visit_context": visit_context, "visit_note": visit_note,
            "grade": grade, "previous_visit": previous_visit, "previous_table": previous["table_no"] if previous else None,
            "previous_menus": previous_menus, "weekly_visits": weekly_visits,
            "is_birthday": birthday, "age": age, "weather_text": weather_text,
            "is_visit_anniversary": anniversary,
            "special_event": special_event, "care_reason": care_reason,
            "service_suggestion": service_suggestion, "most_ordered_menu": most_ordered,
        })
    # 비율별로 등급을 나누지 않고, 실제 오늘 주문 테이블 순서로 안내한다.
    return sorted(result, key=lambda row: (row["today_table"], row["member_id"]))
