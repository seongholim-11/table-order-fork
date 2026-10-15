"""취향과 주문 정보를 반영하는 데모 조합 추천 및 세트 가격 계산."""
from collections import Counter

from menu_data import MENU_BY_ID


from recommendation_data import RULES


def ordered_counts(lines):
    counts = Counter()
    for line in lines:
        if "components" in line:
            for component in line["components"]:
                counts[component["id"]] += component["qty"] * line["qty"]
        else:
            counts[line["id"]] += line["qty"]
    return counts


WEIGHT_STEP = 0.2  # OWNER 추천 가중치(0~100, 기본 50)가 10 높을 때 메뉴당 +2점


def is_late_night(hour):
    return hour is not None and (hour >= 22 or hour < 5)


def item_spicy(item):
    """메뉴의 매운 정도(0~3). 서버 메뉴는 `spicy` 를 갖고, 로컬 더미는 태그로 추정한다."""
    if "spicy" in item:
        return item["spicy"]
    return 2 if "매운맛" in item["tags"] else 0


def recommend_combos(people=2, budget=40000, spicy="상관없어요", drink="맥주", lines=(),
                     menu_by_id=None, hour=None, weather=None, hunger="적당해요", stress="보통",
                     kind="any", intent=None, gender=None, rules=None, member=True):
    """예산/품절/맵기/세트 가능 조건을 지킨 후보를 점수순으로 최대 세 개 반환.

    kind·intent·gender·hour·weather 는 점수에만 약하게 반영하고 조건을 어기게 만들지 않는다
    (그래서 항상 예산 안의 결과가 나온다). 비 오는 날이라고 파전을 밀어 주지는 않는다(뻔한 조합 지양):
    비·눈에는 국물 조합 대신 매콤한 조합을 가산한다.
    조합 할인은 회원에게만 적용한다(member=False 면 정가, 예산도 정가 기준으로 비교).
    """
    menu_by_id = menu_by_id or MENU_BY_ID
    rules = rules or RULES
    discount_percent, drinks, pair_meta = rules["discount_percent"] if member else 0, rules["drinks"], rules["pair_meta"]
    hot_themed, kind_label, intent_label = set(rules["hot_themed"]), rules["kind_label"], rules["intent_label"]
    counts = ordered_counts(lines)
    preferred_categories = Counter()
    for item_id, count in counts.items():
        if item_id in menu_by_id:
            preferred_categories[menu_by_id[item_id]["cat"]] += count
    portions = 2 if people >= 4 else 1
    if hunger == "매우 배고파요":
        portions += 1
    elif hunger == "출출해요" and people >= 3:
        portions = max(portions, 2)
    drink_id = drinks[drink]
    recommendations = []
    for combo_id, title, ids, pairing_reason in rules["pairings"]:
        ids = tuple(ids)
        hot = combo_id in hot_themed
        meta = pair_meta.get(combo_id, {})
        if spicy == "매콤하게":
            ids = tuple(f"{item_id}-hot" if item_id in ("a2", "a3") else item_id for item_id in ids)
        selected_ids = list(ids) + ([drink_id] if drink_id else [])
        if any(item_id not in menu_by_id for item_id in selected_ids):
            continue  # 관리자가 메뉴를 지운 경우
        if any(menu_by_id[item_id]["soldout"] for item_id in selected_ids):
            continue
        if any(not menu_by_id[item_id].get("set_ok", True) for item_id in ids):
            continue  # 세트로 구성할 수 없는 메뉴
        spicy_items = [menu_by_id[item_id] for item_id in ids if item_spicy(menu_by_id[item_id]) >= 2]
        if spicy == "맵지 않게" and (hot or spicy_items):
            continue
        components = []
        for item_id in selected_ids:
            item = menu_by_id[item_id]
            qty = people if item_id == drink_id else portions
            components.append({"id": item_id, "name": item["name"], "emoji": item["emoji"],
                               "qty": qty, "opt": "", "unit": item["price"]})
        original = sum(c["unit"] * c["qty"] for c in components)
        discount = original * discount_percent // 100
        price = original - discount
        if price > budget:
            continue
        popular = sum("BEST" in menu_by_id[item_id]["tags"] for item_id in ids)
        overlap = sum(counts[item_id] > 0 for item_id in ids)
        affinity = sum(min(preferred_categories[menu_by_id[item_id]["cat"]], 3) for item_id in ids)
        owner = sum(menu_by_id[item_id].get("weight", 50) - 50 for item_id in ids) * WEIGHT_STEP
        score = popular * 4 + affinity * 2 - overlap * 15 + owner
        notes = []
        if spicy == "매콤하게":
            score += 20 if spicy_items else -10
            if spicy_items:
                notes.append("선택한 매콤한 취향을 반영했어요.")
        elif spicy == "맵지 않게":
            notes.append("매운맛 메뉴는 제외했어요.")
        if kind not in (None, "any") and kind in meta.get("kinds", ()):
            score += 8
            notes.append(f"원하신 {kind_label[kind]} 위주로 골랐어요.")
        if intent and intent in meta.get("occasions", ()):
            score += 5
            notes.append(f"{intent_label[intent]}에 잘 어울려요.")
        if stress == "높음" and hot and spicy != "맵지 않게":
            score += 4
            notes.append("스트레스가 높은 날엔 칼칼한 맛이 잘 어울려요.")
        if hunger == "매우 배고파요":
            notes.append("배고프다고 하셔서 안주를 한 접시 더 넉넉히 담았어요.")
        if gender == "남자만" and meta.get("mood") == "hearty":
            score += 3
        elif gender == "여자만" and meta.get("mood") == "light":
            score += 3
        if is_late_night(hour) and meta.get("mood") == "light":
            score += 3
            notes.append("늦은 시간이라 부담 적은 안주로 골랐어요.")
        if weather in ("rain", "snow") and hot:
            score += 3
            notes.append("궂은 날씨에 따끈하고 칼칼한 메뉴를 더했어요.")
        elif weather == "hot" and meta.get("mood") == "light":
            score += 2
            notes.append("더운 날씨에 산뜻하게 즐길 수 있어요.")
        score += 3 * (1 - abs(price - budget * .8) / budget)
        reason = f"{people}명이 나눠 먹도록 안주 수량을 맞췄어요. " + pairing_reason
        if notes:
            reason += " " + " ".join(notes)
        if drink != "없이":
            reason += f" {drink}도 1인당 1개씩 포함했어요."
        if counts:
            reason += " " + ("기존 주문과 겹치는 안주가 포함되어 있어요." if overlap else "장바구니·주문 내역의 안주와 겹치지 않게 골랐어요.")
        recommendations.append({"id": combo_id, "name": title, "components": components,
                                "original": original, "discount": discount, "price": price,
                                "reason": reason, "score": score})
    recommendations.sort(key=lambda combo: (-combo["score"], combo["price"], combo["id"]))
    return recommendations[:3]


def combo_cart_line(combo):
    """구성/가격별 세트 행을 만들어 할인 금액을 주문까지 유지."""
    signature = ";".join(f"{c['id']}:{c['qty']}:{c['opt']}" for c in combo["components"])
    key = f"combo:{combo['id']}|{signature}|{combo['price']}"
    description = " + ".join(f"{c['name']} × {c['qty']}" + (f" ({c['opt']})" if c["opt"] else "")
                             for c in combo["components"])
    line = {"id": f"combo:{combo['id']}", "name": f"[AI 조합] {combo['name']}",
            "opt": description, "unit": combo["price"], "original_unit": combo["original"],
            "qty": 1, "components": [dict(c) for c in combo["components"]]}
    return key, line
