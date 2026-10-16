"""매장 데이터에서 근거가 있는 마케팅 추천 카드를 만든다."""

from admin.marketing.config import EMPTY_RECOMMENDATION, RECOMMENDATION_PAGE_SIZE


def _pct(part, whole) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def recommend(ctx: dict) -> list[dict]:
    """각 카드가 title·why·action을 갖도록 규칙 기반 추천을 만든다."""
    members, orders, menus, stats = ctx["members"], ctx["orders"], ctx["menus"], ctx["stats"]
    grades, pool = members["grades"], members["pool_by_grade"]
    cards = []

    dormant = int(grades.get("휴면", 0))
    if dormant:
        sendable = int(pool.get("휴면", 0))
        cards.append({"title": f"휴면 고객 {dormant}명 되찾기",
                      "why": f"전체 회원 {members['total']}명 중 {_pct(dormant, members['total'])}가 한동안 오지 않았어요. 문자를 받을 수 있는 분은 {sendable}명이에요.",
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
    if ai.get("hit_rate") is not None and ai["hit_rate"] < 0.5:
        cards.append({"title": "AI 추천 조합 활용도 높이기",
                      "why": f"AI 추천 적중률이 {ai['hit_rate']:.0%}예요. 아직 추천이 주문으로 잘 이어지지 않아요.",
                      "action": "추천 가중치 화면에서 인기 메뉴 가중치를 올리고, 조합 문구를 매력적으로 다듬어 보세요."})

    if members["opted_out"] or members["sendable"] < members["total"] * 0.5:
        cards.append({"title": "수신 동의 늘리기",
                      "why": f"전체 {members['total']}명 중 문자를 보낼 수 있는 분은 {members['sendable']}명뿐이에요.",
                      "action": "테이블 QR 로그인 시 마케팅 수신 동의를 안내하고, 동의 시 혜택을 약속해 보세요."})
    return cards or [dict(EMPTY_RECOMMENDATION)]


def pick_recommendations(cards: list[dict], round_no: int) -> tuple[list[dict], int, int]:
    """round_no에 해당하는 네 장을 고르고 마지막 묶음은 앞 카드로 채운다."""
    pages = max(1, -(-len(cards) // RECOMMENDATION_PAGE_SIZE))
    page = round_no % pages
    start = page * RECOMMENDATION_PAGE_SIZE
    chosen = cards[start:start + RECOMMENDATION_PAGE_SIZE]
    if len(chosen) < RECOMMENDATION_PAGE_SIZE and pages > 1:
        chosen += cards[:RECOMMENDATION_PAGE_SIZE - len(chosen)]
    return chosen, page + 1, pages

