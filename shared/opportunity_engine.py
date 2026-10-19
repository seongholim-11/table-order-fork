"""회원·주문·메뉴 자료에서 다양한 마케팅 추천을 만드는 공통 규칙 엔진.

백엔드 API와 관리자 더미 화면이 같은 규칙을 사용한다. 입력 행은 두 환경에서
공통으로 맞춘 작은 dict이며, 추천은 확인된 사실과 명시적인 추정만 사용한다.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

PAGE_SIZE = 4
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
EMPTY_RECOMMENDATION = {
    "title": "데이터를 더 모아 볼까요?",
    "why": "아직 주문·회원 데이터가 적어 추천할 근거가 부족해요.",
    "action": "주문이 쌓이면 이곳에 맞춤 마케팅 방법이 나타나요.",
    "action_type": "guide", "target_grades": [], "member_ids": [], "sms_body": "",
}


def _time(value) -> datetime:
    # DB의 UTC 시각도 매장의 한국 시각으로 바꿔 야간·요일·휴면 추천 기준을 맞춘다.
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone(timedelta(hours=9)))


def _date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return _time(value).date()


def _birthday_distance(value: str | None, today: date) -> int | None:
    """카카오 생일 MMDD가 올해/내년 기준 며칠 남았는지 계산한다."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())[-4:]
    if len(digits) != 4:
        return None
    try:
        birthday = date(today.year, int(digits[:2]), int(digits[2:]))
    except ValueError:
        return None
    if birthday < today:
        birthday = birthday.replace(year=today.year + 1)
    return (birthday - today).days


def build_context(members: list[dict], orders: list[dict], menus: list[dict], stats: dict, today: date,
                  rule: dict | None = None) -> dict:
    """정규화된 행을 추천 규칙이 읽는 집계 자료로 바꾼다."""
    # 휴면 고객의 과거 방문 수준도 고객 목록에 저장된 재방문·단골 기준으로 분류한다.
    repeat_min, regular_min = (rule or {}).get("repeat", 2), (rule or {}).get("regular", 5)
    member_by_id = {row["id"]: row for row in members}
    sendable_ids = {row["id"] for row in members if row.get("has_phone") and row.get("marketing_consent")
                    and not row.get("opted_out")}
    grades = Counter(row.get("grade") or "미분류" for row in members)
    pool = Counter(row.get("grade") or "미분류" for row in members if row["id"] in sendable_ids)
    menu_by_name = {row["name"]: row for row in menus}
    quantities, category_qty, hours, weekdays = Counter(), Counter(), Counter(), Counter()
    profiles = defaultdict(lambda: {"orders": 0, "revenue": 0, "qty": Counter(), "cats": Counter(),
                                   "hours": Counter(), "weekdays": Counter(), "pair_like": 0,
                                   "spicy_qty": 0, "mild_qty": 0})

    normalized_orders = []
    for order in orders:
        at = _time(order["ts"])
        lines = order.get("lines", [])
        normalized_orders.append({**order, "at": at})
        hours[at.hour] += 1
        weekdays[at.weekday()] += 1
        member_id = order.get("member_id")
        profile = profiles[member_id] if member_id in member_by_id else None
        total_qty = 0
        for line in lines:
            # AI 조합은 조합 이름이 아니라 실제 구성 메뉴의 취향으로 집계한다.
            sale_lines = [{**component, "qty": int(component.get("qty") or 0) * int(line.get("qty") or 0)}
                          for component in line.get("components", [])] if line.get("components") else [line]
            for sale_line in sale_lines:
                qty = int(sale_line.get("qty") or 0)
                name = sale_line.get("name") or "이름 없는 메뉴"
                quantities[name] += qty
                menu = menu_by_name.get(name) or {}
                category = menu.get("category", "기타")
                category_qty[category] += qty
                if profile is not None:
                    profile["qty"][name] += qty
                    profile["cats"][category] += qty
                    if int(menu.get("spicy") or 0) >= 2:
                        profile["spicy_qty"] += qty
                    else:
                        profile["mild_qty"] += qty
                total_qty += qty
        if profile is not None:
            profile["orders"] += 1
            profile["revenue"] += int(order.get("total") or 0)
            profile["hours"][at.hour] += 1
            profile["weekdays"][at.weekday()] += 1
            if 18 <= at.hour <= 23 and 2 <= total_qty <= 4:
                profile["pair_like"] += 1

    segments: dict[str, list[int]] = {}

    def segment(name: str, predicate) -> None:
        ids = [row["id"] for row in members if predicate(row, profiles.get(row["id"]))]
        if ids:
            segments[name] = ids

    for grade in ("신규", "재방문", "단골", "휴면"):
        segment(f"grade:{grade}", lambda row, _p, grade=grade: row.get("grade") == grade)
    segment("dormant_once", lambda row, _p: row.get("grade") == "휴면" and int(row.get("visit_count") or 0) <= 1)
    segment("dormant_regular", lambda row, _p: row.get("grade") == "휴면" and int(row.get("visit_count") or 0) >= regular_min)
    segment("dormant_repeat", lambda row, _p: row.get("grade") == "휴면" and repeat_min <= int(row.get("visit_count") or 0) < regular_min)
    segment("birthday_30", lambda row, _p: (distance := _birthday_distance(row.get("birthday"), today)) is not None
                                           and distance <= 30)
    for age in ("20대", "30대", "40대", "50대 이상"):
        segment(f"age:{age}", lambda row, _p, age=age: row.get("age_group") == age)
    for gender in ("남", "여"):
        segment(f"gender:{gender}", lambda row, _p, gender=gender: row.get("gender") == gender)

    overall_avg = sum(int(o.get("total") or 0) for o in orders) / len(orders) if orders else 0
    segment("high_value", lambda _row, p: bool(p and p["orders"] >= 2 and p["revenue"] / p["orders"] >= overall_avg * 1.3))
    segment("pair_pattern", lambda _row, p: bool(p and p["orders"] >= 2 and p["pair_like"] / p["orders"] >= .5))
    segment("late_night", lambda _row, p: bool(p and p["orders"] >= 2 and
                                                sum(v for h, v in p["hours"].items() if h >= 22) / p["orders"] >= .5))
    segment("weekend", lambda _row, p: bool(p and p["orders"] >= 2 and
                                             sum(v for d, v in p["weekdays"].items() if d >= 5) / p["orders"] >= .5))
    segment("spicy", lambda _row, p: bool(p and p["spicy_qty"] >= 2 and p["spicy_qty"] > p["mild_qty"]))
    segment("mild", lambda _row, p: bool(p and p["mild_qty"] >= 2 and p["mild_qty"] > p["spicy_qty"] * 2))
    for category in sorted({row.get("category", "기타") for row in menus}):
        segment(f"cat:{category}", lambda _row, p, category=category: bool(
            p and sum(p["cats"].values()) >= 2 and p["cats"][category] / sum(p["cats"].values()) >= .5))
    for name, _quantity in quantities.most_common(5):
        segment(f"favorite:{name}", lambda _row, p, name=name: bool(
            p and sum(p["qty"].values()) >= 2 and p["qty"][name] / sum(p["qty"].values()) >= .5))
    for name in (row["name"] for row in menus if row.get("soldout")):
        segment(f"dormant_soldout:{name}", lambda row, p, name=name: bool(
            row.get("grade") == "휴면" and p and p["qty"][name] > 0))

    return {
        "stats": stats,
        "members": {"total": len(members), "grades": dict(grades), "sendable": len(sendable_ids),
                    "opted_out": sum(bool(row.get("opted_out")) for row in members),
                    "pool_by_grade": dict(pool), "sendable_ids": sendable_ids,
                    "rows": members, "segments": segments},
        "orders": {"count": len(orders), "revenue": sum(int(o.get("total") or 0) for o in orders),
                   "avg": round(overall_avg), "peak_hours": [h for h, _ in hours.most_common(5)],
                   "weekdays": weekdays.most_common(), "top_items": quantities.most_common(10),
                   "category_qty": category_qty.most_common(), "rows": normalized_orders},
        "menus": {"total": len(menus), "rows": menus,
                  "soldout": [m["name"] for m in menus if m.get("soldout")],
                  "high_weight": [m["name"] for m in sorted(menus, key=lambda m: m.get("weight", 0), reverse=True)[:5]],
                  "unsold": [m["name"] for m in menus if not m.get("soldout") and quantities[m["name"]] == 0]},
        "profiles": profiles,
    }


def recommend(ctx: dict) -> list[dict]:
    """고객·행동·취향 세그먼트를 조합해 수십 개의 근거 있는 카드를 만든다."""
    members, orders, menus = ctx["members"], ctx["orders"], ctx["menus"]
    if not members["total"] and not orders["count"]:
        return [dict(EMPTY_RECOMMENDATION)]
    rows = {row["id"]: row for row in members["rows"]}
    segments = members["segments"]
    cards: list[dict] = []

    def add(title, why, action, ids=None, body="", action_type="guide"):
        ids = list(ids or [])
        sendable = [member_id for member_id in ids if member_id in members["sendable_ids"]]
        grades = sorted({rows[i].get("grade") for i in sendable if rows[i].get("grade")})
        cards.append({"title": title, "why": why, "action": action,
                      "action_type": action_type if sendable and body else "guide",
                      "target_grades": grades, "member_ids": sendable,
                      "sms_body": body if action_type == "sms" and sendable else ""})

    def ids(name):
        return segments.get(name, [])

    # 고객 생애주기: 같은 등급도 원인과 실행 방법을 나눠 한 카드로 뭉개지 않는다.
    lifecycle = [
        ("신규", "첫 방문 감사", "첫 방문의 좋은 기억이 식기 전에 두 번째 방문 이유를 만들어야 해요.",
         "첫 방문 감사와 다음 방문 혜택을 문자로 안내하세요.", "첫 방문 감사드려요. 다음 방문 때 보여주시면 음료 1잔을 서비스로 드릴게요."),
        ("신규", "신규 고객 메뉴 안내", "아직 매장의 대표 메뉴를 충분히 경험하지 못한 고객층이에요.",
         "다음 방문 시 대표 메뉴를 경험했는지 확인하고 잘 맞는 조합을 현장에서 제안하세요.", ""),
        ("재방문", "세 번째 방문 유도", "두 번째 방문까지 이어진 고객은 단골로 전환될 가능성이 높은 구간이에요.",
         "다음 방문 시 작은 서비스로 단골 전환을 유도하세요.", "다시 찾아주셔서 감사해요. 다음 방문에는 작은 서비스 안주를 준비해 둘게요."),
        ("재방문", "재방문 고객 취향 확인", "반복 주문이 쌓이기 시작해 개인 취향 추천의 정확도를 높일 수 있어요.",
         "다음 방문 시 이전 주문을 참고해 선호하는 맛과 메뉴를 확인하고 응대에 반영하세요.", ""),
        ("단골", "단골 감사 혜택", "방문 횟수가 높은 핵심 고객은 유지가 신규 유치만큼 중요해요.",
         "단골 전용 감사 서비스를 안내하세요.", "늘 찾아주셔서 감사해요. 방문하시면 음료 1잔을 서비스로 드릴게요."),
        ("단골", "신메뉴 선공개", "매장을 잘 아는 단골의 반응은 새 메뉴 검증에도 좋은 근거가 돼요.",
         "실제 신메뉴가 준비되면 방문한 단골에게 먼저 소개하고 반응을 기록하세요.", ""),
        ("휴면", "휴면 고객 복귀", "마지막 방문 후 휴면 기준을 넘겨 자연 재방문 가능성이 낮아진 고객층이에요.",
         "부담 없는 복귀 혜택과 함께 다시 초대하세요.", "오랜만에 뵙고 싶어요. 이번 주 방문하시면 안주 10% 할인해 드릴게요."),
        ("휴면", "휴면 원인 확인", "최근 방문이 끊겼다는 사실만으로 원인을 단정할 수는 없어요. 혜택·메뉴·경험 중 무엇이 문제였는지 가볍게 확인해야 해요.",
         "짧은 선택형 의견 요청과 복귀 혜택을 함께 보내세요.", "요즘 뵙지 못해 아쉬워요. 메뉴·가격·서비스 중 아쉬웠던 점을 알려주시면 다음 방문에 반영할게요."),
    ]
    for grade, title, reason, action, body in lifecycle:
        group = ids(f"grade:{grade}")
        if group:
            # 감사 혜택·재방문·휴면 복귀처럼 구체적인 방문 계기가 있는 경우에만 문자를 제안한다.
            add(f"{title} · {len(group)}명", reason, action, group, body,
                action_type="sms" if body else "guide")

    dormant_rules = [
        ("dormant_once", "한 번 방문 후 멈춘 휴면 고객", "첫 경험이 두 번째 방문의 충분한 이유로 이어지지 않았을 가능성이 커요.",
         "첫 방문 고객 전용 복귀 혜택을 제안하세요.", "첫 방문 이후 다시 뵙지 못했어요. 재방문해 주시면 음료 1잔을 서비스로 드릴게요."),
        ("dormant_repeat", "재방문하다 멈춘 휴면 고객", "재방문 기준을 충족한 뒤 방문이 끊긴 고객은 메뉴 변화나 혜택 부족이 원인일 가능성을 점검할 필요가 있어요.",
         "새 메뉴 소식과 복귀 혜택을 함께 알리세요.", "전에 찾아주셨던 기억이 나요. 새 메뉴도 준비했으니 이번 주 다시 들러 주세요."),
        ("dormant_regular", "예전 단골이 된 휴면 고객", "방문 횟수는 높지만 오래 오지 않아 관계가 약해진 상태일 가능성이 커요.",
         "일반 광고보다 기억하고 있다는 개인화된 감사 문자를 보내세요.", "자주 찾아주셨던 고객님이 생각났어요. 다시 오시면 감사 서비스로 반갑게 맞아드릴게요."),
    ]
    for key, title, reason, action, body in dormant_rules:
        if ids(key):
            add(f"{title} · {len(ids(key))}명", reason, action, ids(key), body, action_type="sms")

    if ids("birthday_30"):
        add(f"30일 안에 생일인 고객 · {len(ids('birthday_30'))}명", "회원가입 때 동의해 제공한 생일이 가까운 고객이에요.",
            "생일 축하와 방문 혜택을 미리 안내하세요.", ids("birthday_30"),
            "생일을 미리 축하드려요! 생일이 있는 달에 방문하시면 작은 축하 서비스를 준비해 드릴게요.",
            action_type="sms")

    # 인구통계는 취향을 단정하지 않고 실제 주문 반응을 실험할 모수로만 쓴다.
    for key, label in [("age:20대", "20대"), ("age:30대", "30대"), ("age:40대", "40대"),
                       ("age:50대 이상", "50대 이상"), ("gender:남", "남성"), ("gender:여", "여성")]:
        if ids(key):
            add(f"{label} 고객 반응 실험 · {len(ids(key))}명", f"현재 {label} 고객이 {len(ids(key))}명 있어 충분한 표본으로 반응을 비교할 수 있어요. 성별·연령만으로 취향을 단정하지는 않아요.",
                "연령·성별만으로 문자를 보내기보다 실제 주문 메뉴와 방문 반응을 비교해 현장 추천을 조정하세요.", ids(key))

    category_labels = {"chicken": "치킨", "anju": "안주", "soup": "탕", "beer": "맥주",
                       "soju": "소주", "side": "사이드", "기타": "다양한 메뉴"}
    for category, _qty in orders["category_qty"]:
        group = ids(f"cat:{category}")
        if group:
            label = category_labels.get(category, category)
            add(f"{label} 선호 고객 · {len(group)}명", f"회원별 주문 수량의 절반 이상이 {label} 카테고리에 모인 고객층이에요.",
                f"다음 방문 시 이전 주문을 참고해 {label}와 잘 맞는 곁들임 메뉴를 현장에서 제안하세요.", group)

    for name, _quantity in orders["top_items"][:5]:
        group = ids(f"favorite:{name}")
        if group:
            add(f"‘{name}’ 선호 고객 · {len(group)}명", f"회원별 주문 수량의 절반 이상이 ‘{name}’에 모인 고객층이에요.",
                f"다음 방문 시 ‘{name}’의 판매 가능 여부를 확인하고 어울리는 곁들임 메뉴를 제안하세요.", group)

    for key, title, reason, action in [
        ("spicy", "매운맛 선호 고객", "매운 정도 2단계 이상 메뉴의 주문 비중이 더 높아요.",
         "다음 방문 시 매운맛 선호를 확인한 뒤, 주문 메뉴의 맵기를 취향에 맞춰 준비할 수 있는지 안내하세요."),
        ("mild", "순한맛 선호 고객", "맵지 않은 메뉴 주문이 매운 메뉴보다 두 배 이상 많아요.",
         "다음 방문 시 순한맛 선호를 확인하고 맵지 않은 메뉴나 조절 가능한 맵기를 안내하세요."),
    ]:
        if ids(key):
            add(f"{title} · {len(ids(key))}명", reason, action, ids(key))

    for name in menus["soldout"]:
        group = ids(f"dormant_soldout:{name}")
        if group:
            add(f"선호 메뉴 품절 후 휴면 가능성 · {len(group)}명", f"휴면 고객의 이전 주문에 ‘{name}’이 있지만 지금은 품절입니다. 품절이 이탈 원인이라고 단정할 수는 없지만 확인할 가치가 있어요.",
                "실제 재입고나 대체 메뉴가 준비됐는지 확인한 뒤 복귀 안내를 보내세요.", group,
                f"전에 드셨던 ‘{name}’의 판매 상황과 대체 메뉴를 안내해 드리고 싶어요. 방문 전에 편하게 문의해 주세요.",
                action_type="sms")

    special_segments = [
        ("high_value", "객단가가 높은 고객", "주문 2건 이상이며 개인 평균 주문금액이 전체 평균보다 30% 이상 높아요.",
         "다음 방문 시 선호 메뉴를 확인하고 신메뉴 시식이나 세심한 서비스를 제안하세요.", ""),
        ("pair_pattern", "데이트·2인 방문 가능성 높은 고객", "저녁 주문 중 메뉴 수량 2~4개 패턴이 절반 이상입니다. 연인 여부를 저장한 것은 아니며 2인 방문 가능성에 대한 추정이에요.",
         "실제 방문 인원을 확인한 뒤 2인에게 적당한 메뉴 수량과 조합을 현장에서 제안하세요.", ""),
        ("late_night", "늦은 시간 방문 고객", "회원 주문의 절반 이상이 22시 이후에 발생했어요.",
         "늦은 시간 방문에 대비해 가벼운 안주와 빠르게 준비할 수 있는 메뉴를 점검하세요.", ""),
        ("weekend", "주말 중심 방문 고객", "회원 주문의 절반 이상이 토·일요일에 발생했어요.",
         "주말 방문 수요에 맞춰 선호 메뉴의 재고와 좌석·인력 준비를 점검하세요.", ""),
    ]
    for key, title, reason, action, body in special_segments:
        if ids(key):
            add(f"{title} · {len(ids(key))}명", reason, action, ids(key), body)

    # 매장 전체 주문 패턴도 여러 관점으로 나눠 운영 제안에 사용한다.
    for rank, (name, quantity) in enumerate(orders["top_items"][:5], 1):
        add(f"인기 메뉴 {rank}위 ‘{name}’ 활용", f"누적 판매 수량 {quantity}개로 실제 주문 반응이 확인됐어요.",
            "메뉴판과 현장 추천에 인기 메뉴 조합을 반영하고 재고를 충분히 준비하세요.")
    for hour in orders["peak_hours"][:3]:
        add(f"{hour}시 주문 집중 완화", f"전체 주문 기록에서 {hour}시가 상위 혼잡 시간대예요.",
            "혼잡 시간대의 인력·재료를 미리 준비하고 주문 동선을 점검하세요.")
    for weekday, count in orders["weekdays"][:3]:
        label = WEEKDAYS[weekday]
        add(f"{label}요일 방문 수요 활용", f"{label}요일 주문이 {count}건으로 상위권이에요.",
            "해당 요일의 좌석·인력·인기 메뉴 재고를 미리 준비하세요.")

    for name in menus["high_weight"][:3]:
        add(f"추천 가중치 메뉴 ‘{name}’ 검증", "현재 추천 가중치가 높은 메뉴라 노출 대비 주문 반응을 확인할 필요가 있어요.",
            "AI 노출 후 주문 전환을 비교해 가중치를 유지하거나 조정하세요.", action_type="guide")
    for name in menus["unsold"][:3]:
        add(f"미판매 메뉴 ‘{name}’ 진단", "현재 주문 기록에는 판매 수량이 없어요. 인지도·가격·구성 중 원인을 확인해야 해요.",
            "인기 메뉴와 묶어 짧게 시험한 뒤 반응이 없으면 구성을 재검토하세요.", action_type="guide")
    if menus["soldout"]:
        add("품절 메뉴 대체 추천", f"{', '.join(menus['soldout'][:3])} 메뉴가 품절 상태예요.",
            "비슷한 가격·종류의 판매 가능 메뉴를 추천 영역에 먼저 노출하세요.", action_type="guide")
    ai = ctx["stats"].get("ai", {})
    if ai.get("hit_rate") is not None:
        add("AI 추천 전환율 점검", f"현재 추천 노출 대비 AI 조합 주문 비율은 {ai['hit_rate']:.0%}예요.",
            "추천 문구·메뉴 가중치를 하나씩 바꾸고 전환율 변화를 비교하세요.", action_type="guide")
    if members["sendable"] < members["total"]:
        add("문자 도달 가능 고객 늘리기", f"전체 {members['total']}명 중 전화번호와 동의가 확인된 고객은 {members['sendable']}명이에요.",
            "로그인 화면에서 활용 목적과 혜택을 투명하게 안내해 자발적 동의를 받으세요.", action_type="guide")

    # 같은 제목이 생기지 않도록 제거하고, 실제 데이터가 충분하면 수십 개가 순서대로 노출된다.
    unique = list({card["title"]: card for card in cards}.values())
    if not unique:
        return [dict(EMPTY_RECOMMENDATION)]
    # 마지막 화면도 네 가지를 유지하되 앞 추천을 복사하지 않는다. 부족한 칸에는 실제 집계값을
    # 해석할 때 필요한 운영 원칙을 서로 다른 고유 카드로 보충한다.
    quality_guides = [
        ("추천 근거 정기 점검", f"현재 회원 {members['total']}명과 주문 {orders['count']}건을 기준으로 분석했어요.",
         "회원·주문 데이터가 늘어난 뒤 같은 추천의 대상 수가 어떻게 달라지는지 다시 확인하세요."),
        ("마케팅 실험은 한 번에 하나씩", f"현재 평균 주문금액은 {orders['avg']:,}원이에요. 여러 혜택을 동시에 바꾸면 어떤 변화가 효과였는지 알기 어려워요.",
         "문구·대상·혜택 중 하나만 바꾸고 평균 주문금액과 재방문 변화를 비교하세요."),
        ("성과 기록 기준 통일", f"문자를 보낼 수 있는 고객은 전체 {members['total']}명 중 {members['sendable']}명이에요.",
         "발송 대상·방문·주문을 같은 기간으로 기록해 다음 추천의 근거로 사용하세요."),
    ]
    for title, why, action in quality_guides[:(-len(unique)) % PAGE_SIZE]:
        unique.append({"title": title, "why": why, "action": action, "action_type": "guide",
                       "target_grades": [], "member_ids": [], "sms_body": ""})
    return unique


def _recommendation_page(cards: list[dict], round_no: int) -> dict:
    """네 장씩 겹치지 않게 보여 주고, 모든 추천을 본 뒤에만 처음으로 돌아간다."""
    pages = max(1, -(-len(cards) // PAGE_SIZE))
    page_index = round_no % pages
    start = page_index * PAGE_SIZE
    # 마지막 묶음이 네 장보다 적더라도 첫 카드로 채우지 않는다. 그래야 한 순환 안에서는
    # 같은 추천이 다시 나오지 않고, 모든 추천을 확인한 다음 묶음에서만 처음으로 돌아간다.
    chosen = cards[start:start + PAGE_SIZE]
    return {"items": chosen, "page": page_index + 1, "pages": pages, "total": len(cards)}


def pick_recommendations(cards: list[dict], round_no: int) -> dict:
    """기존 목록과 함께 문자·기타 추천을 각각 네 장씩 순환할 수 있게 제공한다."""
    result = _recommendation_page(cards, round_no)
    # 분류 후 페이지를 나눠야 문자 추천이 많은 경우에도 기타 추천을 바로 볼 수 있다.
    result["groups"] = {
        kind: _recommendation_page([card for card in cards if card.get("action_type") == kind], round_no)
        for kind in ("sms", "guide")
    }
    return result
