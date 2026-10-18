"""DB에서 읽은 매장 데이터로 관리자 마케팅 추천 카드를 만든다."""

from collections import Counter

from app.services.grades import grade_of

PAGE_SIZE = 4
EMPTY_RECOMMENDATION = {
    "title": "데이터를 더 모아 볼까요?",
    "why": "아직 주문·회원 데이터가 적어 추천할 근거가 부족해요.",
    "action": "주문이 쌓이면 이곳에 맞춤 마케팅 방법이 나타나요.",
}


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def build_context(orders: list[dict], members: list[dict], menus: list[dict], stats: dict,
                  today, rule: dict) -> dict:
    """DB 행을 화면의 기존 추천 규칙이 읽는 작은 요약 자료로 바꾼다."""
    grades = Counter(grade_of(member, today, **rule) for member in members)
    sendable = [member for member in members if member.get("phone") and member.get("marketing_consent")
                and not member.get("opted_out")]
    pool = Counter(grade_of(member, today, **rule) for member in sendable)

    quantities, hours = Counter(), Counter()
    for order in orders:
        # 주문 시간 형식은 통계 서비스에서 이미 KST로 통일하는 함수를 재사용한다.
        from app.services.stats import order_time
        hours[order_time(order["ts"]).hour] += 1
        for line in order.get("lines", []):
            if line.get("kind") == "combo" or str(line.get("id", "")).startswith("combo:"):
                for component in line.get("components", []):
                    quantities[component["name"]] += component["qty"] * line["qty"]
            else:
                quantities[line["name"]] += line["qty"]

    on_sale = [menu for menu in menus if not menu.get("soldout")]
    return {
        "stats": stats,
        "members": {
            "total": len(members), "grades": dict(grades), "sendable": len(sendable),
            "opted_out": sum(bool(member.get("opted_out")) for member in members),
            "pool_by_grade": dict(pool),
        },
        "orders": {
            "count": len(orders), "revenue": sum(order["total"] for order in orders),
            "avg": sum(order["total"] for order in orders) // len(orders) if orders else 0,
            "peak_hours": [hour for hour, _ in hours.most_common(3)],
            "top_items": quantities.most_common(5),
        },
        "menus": {
            "total": len(menus), "on_sale": len(on_sale),
            "soldout": [menu["name"] for menu in menus if menu.get("soldout")],
            "high_weight": [menu["name"] for menu in sorted(
                menus, key=lambda menu: menu.get("weight", 0), reverse=True)[:3]],
            "unsold": [menu["name"] for menu in on_sale if quantities[menu["name"]] == 0],
        },
    }


def recommend(ctx: dict) -> list[dict]:
    """기존 관리자 화면과 같은 조건으로 근거·실행 방법이 있는 카드를 만든다."""
    members, orders, menus, stats = ctx["members"], ctx["orders"], ctx["menus"], ctx["stats"]
    # 회원과 주문이 모두 없으면 시드 메뉴만으로 억지 추천을 만들지 않는다.
    if not members["total"] and not orders["count"]:
        return [dict(EMPTY_RECOMMENDATION)]

    grades, pool, cards = members["grades"], members["pool_by_grade"], []
    dormant = int(grades.get("휴면", 0))
    if dormant:
        cards.append({"title": f"휴면 고객 {dormant}명 되찾기",
                      "why": f"전체 회원 {members['total']}명 중 {_pct(dormant, members['total'])}가 한동안 오지 않았어요. "
                             f"문자를 받을 수 있는 분은 {int(pool.get('휴면', 0))}명이에요.",
                      "action": "‘휴면’ 등급에게 재방문 쿠폰 문자(예: 안주 10% 할인)를 보내 보세요."})
    regular = int(grades.get("단골", 0))
    if regular:
        cards.append({"title": f"단골 {regular}명에게 감사 혜택",
                      "why": "단골은 매출의 중심이고, 작은 혜택만으로도 발길이 이어져요.",
                      "action": "단골 전용 서비스 안주나 감사 문자를 보내 보세요."})
    repeat, new = int(grades.get("재방문", 0)), int(grades.get("신규", 0))
    if new:
        cards.append({"title": f"신규 {new}명을 재방문 고객으로",
                      "why": f"재방문 고객은 {repeat}명이에요. 첫 방문 뒤 한 번 더 오게 하는 것이 가장 효율적이에요.",
                      "action": "신규 등급에게 ‘다음 방문 시 음료 1병 서비스’ 문자를 보내 보세요."})
    if orders["peak_hours"]:
        hours = ", ".join(f"{hour}시" for hour in sorted(orders["peak_hours"]))
        cards.append({"title": f"한가한 시간대 이벤트 (피크: {hours})",
                      "why": f"주문이 {hours}에 몰려 있어요. 그 외 시간은 비어 있을 가능성이 커요.",
                      "action": "피크가 아닌 시간대 한정 할인(해피아워)을 만들고 수신 동의 고객에게 알려 보세요."})
    if orders["top_items"]:
        name, quantity = orders["top_items"][0]
        cards.append({"title": f"인기 메뉴 ‘{name}’ 앞세우기",
                      "why": f"주문 수량 {quantity}개로 1위예요. 사진과 문구로 먼저 보이게 하면 객단가가 올라가요.",
                      "action": f"‘{name}’을 세트 구성에 넣거나 추천 가중치를 올려 보세요."})
    if menus["high_weight"]:
        name = menus["high_weight"][0]
        cards.append({"title": f"추천 메뉴 ‘{name}’ 집중 노출",
                      "why": "현재 추천 가중치가 가장 높은 메뉴예요. 실제 주문 반응과 함께 확인할 수 있어요.",
                      "action": "AI 추천 영역의 노출과 주문 반응을 확인하고 가중치를 조정해 보세요."})
    if menus["unsold"]:
        names = ", ".join(menus["unsold"][:3])
        cards.append({"title": "안 팔리는 메뉴 살리기",
                      "why": f"{names} 등 {len(menus['unsold'])}개 메뉴는 아직 주문이 없어요.",
                      "action": "인기 메뉴와 묶은 세트로 만들거나, 추천 가중치를 올려 노출을 늘려 보세요."})
    if menus["soldout"]:
        cards.append({"title": "품절 메뉴 정리",
                      "why": f"{', '.join(menus['soldout'][:3])} 품절 상태라 손님이 아쉬워할 수 있어요.",
                      "action": "재입고 일정을 정하거나 대체 메뉴를 추천 목록에 올려 두세요."})
    ai = stats.get("ai", {})
    if ai.get("hit_rate") is not None and ai["hit_rate"] < .5:
        cards.append({"title": "AI 추천 조합 활용도 높이기",
                      "why": f"AI 추천 적중률이 {ai['hit_rate']:.0%}예요. 아직 추천이 주문으로 잘 이어지지 않아요.",
                      "action": "추천 가중치 화면에서 인기 메뉴 가중치를 올리고, 조합 문구를 매력적으로 다듬어 보세요."})
    if members["opted_out"] or members["sendable"] < members["total"] * .5:
        cards.append({"title": "수신 동의 늘리기",
                      "why": f"전체 {members['total']}명 중 문자를 보낼 수 있는 분은 {members['sendable']}명뿐이에요.",
                      "action": "테이블 QR 로그인 시 마케팅 수신 동의를 안내하고, 동의 시 혜택을 약속해 보세요."})
    return cards or [dict(EMPTY_RECOMMENDATION)]


def pick_recommendations(cards: list[dict], round_no: int) -> dict:
    """요청한 회차의 네 장을 고르고 마지막 묶음은 첫 카드부터 채운다."""
    pages = max(1, -(-len(cards) // PAGE_SIZE))
    page_index = round_no % pages
    start = page_index * PAGE_SIZE
    chosen = cards[start:start + PAGE_SIZE]
    if len(chosen) < PAGE_SIZE and pages > 1:
        chosen += cards[:PAGE_SIZE - len(chosen)]
    return {"items": chosen, "page": page_index + 1, "pages": pages}


def opportunities(orders: list[dict], members: list[dict], menus: list[dict], stats: dict,
                  today, rule: dict, round_no: int) -> dict:
    """라우터가 DB 자료를 한 번씩 읽어 넘기면 추천 페이지 응답을 완성한다."""
    return pick_recommendations(recommend(build_context(orders, members, menus, stats, today, rule)), round_no)
