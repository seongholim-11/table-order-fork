"""마케팅 > AI 탭의 두뇌: 컨텍스트 수집 → 마케팅 추천 → 챗봇 답변.

화면(app.py)은 여기서 `build_context`, `recommend`, `get_client().reply` 세 가지만 쓴다.
지금은 LLM API 키 없이 동작하도록 규칙 기반(RuleBasedClient)으로 답한다.

실제 Claude API 로 바꾸는 지점: ClaudeClient.reply (아래) 한 곳. 컨텍스트 dict 를 `context_to_text` 로
프롬프트에 넣고 대화 기록(history)과 함께 보내면 된다. 그 뒤 get_client() 가 ClaudeClient 를 돌려주게만 바꾸면
화면 코드는 그대로다.
"""
import os
from collections import Counter
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

import httpx

import admin_repository as repo_mod
from admin_dummy_data import Unsupported

GRADE_ORDER = ["신규", "재방문", "단골", "휴면"]


def build_context(repo, rule: dict) -> dict:
    """다른 admin 페이지(대시보드·메뉴·고객 등급·주문 이력·마케팅)의 데이터를 한 덩어리로 모은다."""
    stats = repo.stats(rule)
    menus, members, orders = repo.menus(), repo.members(rule), repo.orders()
    try:
        sms_logs, sms_usage = repo.sms_logs(), repo.sms_usage()
    except (Unsupported, repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        sms_logs, sms_usage = [], None  # 문자 기능을 못 쓰는 환경에서도 AI 탭은 동작해야 한다

    pool = members[members["마케팅 수신 동의"] & ~members["수신거부"]] if len(members) else members
    on_sale = menus[menus["판매 여부"]] if len(menus) else menus
    line_qty: Counter = Counter()
    for text in orders["주문 내역"] if len(orders) else []:
        for part in text.split(", "):
            name, _, qty = part.rpartition(" x")
            if name:
                line_qty[name] += int(qty or 1)
    hours = Counter(t.hour for t in orders["주문 시각"]) if len(orders) else Counter()
    weekdays = Counter(t.weekday() for t in orders["주문 시각"]) if len(orders) else Counter()
    return {
        "stats": stats,
        "menus": {"total": len(menus), "on_sale": len(on_sale),
                  "soldout": [] if not len(menus) else menus[~menus["판매 여부"]]["메뉴명"].tolist(),
                  "high_weight": [] if not len(menus) else menus.nlargest(3, "추천 가중치")["메뉴명"].tolist(),
                  "unsold": [n for n in (on_sale["메뉴명"].tolist() if len(on_sale) else []) if line_qty[n] == 0]},
        "members": {"total": len(members), "grades": dict(members["등급"].value_counts()) if len(members) else {},
                    "sendable": len(pool), "opted_out": int(members["수신거부"].sum()) if len(members) else 0,
                    "pool_by_grade": dict(pool["등급"].value_counts()) if len(pool) else {}},
        "orders": {"count": len(orders), "revenue": int(orders["금액"].sum()) if len(orders) else 0,
                   "avg": int(orders["금액"].mean()) if len(orders) else 0,
                   "peak_hours": [h for h, _ in hours.most_common(3)],
                   "busy_weekday": weekdays.most_common(1)[0][0] if weekdays else None,
                   "top_items": line_qty.most_common(5)},
        "sms": {"logs": len(sms_logs), "usage": sms_usage},
    }


def _pct(part, whole) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def recommend(ctx: dict) -> list[dict]:
    """사장님께 드리는 마케팅 방법. 각 항목: {title, why, action}. 데이터에서 근거를 찾은 것만 낸다."""
    m, o, mn, st = ctx["members"], ctx["orders"], ctx["menus"], ctx["stats"]
    grades, pool = m["grades"], m["pool_by_grade"]
    recs = []
    dormant = int(grades.get("휴면", 0))
    if dormant:
        n = int(pool.get("휴면", 0))
        recs.append({"title": f"휴면 고객 {dormant}명 되찾기",
                     "why": f"전체 회원 {m['total']}명 중 {_pct(dormant, m['total'])}가 한동안 오지 않았어요. 문자를 받을 수 있는 분은 {n}명이에요.",
                     "action": "‘휴면’ 등급에게 재방문 쿠폰 문자(예: 안주 10% 할인)를 보내 보세요. 마케팅 > AI 문자 탭의 ‘빠른 문구’를 쓰면 돼요."})
    regular = int(grades.get("단골", 0))
    if regular:
        recs.append({"title": f"단골 {regular}명에게 감사 혜택",
                     "why": "단골은 매출의 중심이고, 작은 혜택만으로도 발길이 이어져요.",
                     "action": "단골 전용 서비스 안주나 감사 문자를 보내 보세요."})
    repeat, new = int(grades.get("재방문", 0)), int(grades.get("신규", 0))
    if new:
        recs.append({"title": f"신규 {new}명을 재방문 고객으로",
                     "why": f"재방문 고객은 {repeat}명이에요. 첫 방문 뒤 한 번 더 오게 하는 것이 가장 효율적이에요.",
                     "action": "신규 등급에게 ‘다음 방문 시 음료 1병 서비스’ 문자를 보내 보세요."})
    if o["peak_hours"]:
        hrs = ", ".join(f"{h}시" for h in sorted(o["peak_hours"]))
        recs.append({"title": f"한가한 시간대 이벤트 (피크: {hrs})",
                     "why": f"주문이 {hrs}에 몰려 있어요. 그 외 시간은 비어 있을 가능성이 커요.",
                     "action": "피크가 아닌 시간대 한정 할인(해피아워)을 만들고 수신 동의 고객에게 알려 보세요."})
    if o["top_items"]:
        name, qty = o["top_items"][0]
        recs.append({"title": f"인기 메뉴 ‘{name}’ 앞세우기",
                     "why": f"주문 수량 {qty}개로 1위예요. 사진과 문구로 먼저 보이게 하면 객단가가 올라가요.",
                     "action": f"‘{name}’을 세트 구성에 넣거나 추천 가중치를 올려 보세요."})
    if mn["unsold"]:
        names = ", ".join(mn["unsold"][:3])
        recs.append({"title": "안 팔리는 메뉴 살리기",
                     "why": f"{names} 등 {len(mn['unsold'])}개 메뉴는 아직 주문이 없어요.",
                     "action": "인기 메뉴와 묶은 세트로 만들거나, 추천 가중치를 올려 노출을 늘려 보세요."})
    if mn["soldout"]:
        recs.append({"title": "품절 메뉴 정리",
                     "why": f"{', '.join(mn['soldout'][:3])} 품절 상태라 손님이 아쉬워할 수 있어요.",
                     "action": "재입고 일정을 정하거나 대체 메뉴를 추천 목록에 올려 두세요."})
    ai = st["ai"]
    if ai.get("hit_rate") is not None and ai["hit_rate"] < 0.5:
        recs.append({"title": "AI 추천 조합 활용도 높이기",
                     "why": f"AI 추천 적중률이 {ai['hit_rate']:.0%}예요. 아직 추천이 주문으로 잘 이어지지 않아요.",
                     "action": "추천 가중치 화면에서 인기 메뉴 가중치를 올리고, 조합 문구를 매력적으로 다듬어 보세요."})
    if m["opted_out"] or m["sendable"] < m["total"] * 0.5:
        recs.append({"title": "수신 동의 늘리기",
                     "why": f"전체 {m['total']}명 중 문자를 보낼 수 있는 분은 {m['sendable']}명뿐이에요.",
                     "action": "테이블 QR 로그인 시 마케팅 수신 동의를 안내하고, 동의 시 혜택을 약속해 보세요."})
    return recs or [{"title": "데이터를 더 모아 볼까요?", "why": "아직 주문·회원 데이터가 적어 추천할 근거가 부족해요.",
                     "action": "주문이 쌓이면 이곳에 맞춤 마케팅 방법이 나타나요."}]


def context_to_text(ctx: dict) -> str:
    """실제 LLM 에 넘길 때 시스템 프롬프트에 붙일 컨텍스트 요약 (ClaudeClient 에서 사용)."""
    m, o, mn = ctx["members"], ctx["orders"], ctx["menus"]
    return (f"회원 {m['total']}명(등급 {m['grades']}), 문자 발송 가능 {m['sendable']}명, 수신거부 {m['opted_out']}명. "
            f"주문 {o['count']}건, 매출 {o['revenue']}원, 평균 {o['avg']}원, 피크 시간 {o['peak_hours']}, 인기 메뉴 {o['top_items']}. "
            f"메뉴 {mn['total']}개(판매 중 {mn['on_sale']}), 품절 {mn['soldout']}, 주문 없는 메뉴 {mn['unsold']}. "
            f"문자 발송 내역 {ctx['sms']['logs']}건.")


class RuleBasedClient:
    """키워드로 질문을 분류해 컨텍스트 숫자로 답한다. 외부 호출 없음."""

    def reply(self, question: str, ctx: dict, history: list[dict] | None = None) -> str:
        q = question.replace(" ", "")
        m, o, mn = ctx["members"], ctx["orders"], ctx["menus"]
        recs = recommend(ctx)
        if any(k in q for k in ("휴면", "안오", "재방문", "단골")):
            g = m["grades"]
            return (f"현재 등급별 회원은 " + ", ".join(f"{k} {int(g.get(k, 0))}명" for k in GRADE_ORDER)
                    + f"예요. 문자 발송 가능 인원은 {m['sendable']}명이에요.\n\n"
                    + "추천: " + recs[0]["title"] + " — " + recs[0]["action"])
        if any(k in q for k in ("인기", "메뉴", "안주", "많이팔")):
            if not o["top_items"]:
                return "아직 주문 데이터가 없어서 인기 메뉴를 알 수 없어요."
            top = ", ".join(f"{n}({c}개)" for n, c in o["top_items"][:3])
            extra = f" 주문이 없는 메뉴는 {', '.join(mn['unsold'][:3])} 등이에요." if mn["unsold"] else ""
            return f"가장 많이 팔린 메뉴는 {top}예요.{extra} 인기 메뉴를 세트에 묶어 홍보해 보세요."
        if any(k in q for k in ("시간", "피크", "한가", "요일")):
            if not o["peak_hours"]:
                return "아직 주문 시간 데이터가 부족해요."
            return (f"주문이 가장 많은 시간대는 {', '.join(f'{h}시' for h in sorted(o['peak_hours']))}예요. "
                    "그 외 시간대에 한정 할인을 걸면 빈 시간을 채울 수 있어요.")
        if any(k in q for k in ("매출", "객단가", "평균", "금액")):
            return (f"누적 주문 {o['count']}건, 매출 {o['revenue']:,}원, 평균 주문금액 {o['avg']:,}원이에요. "
                    "세트 메뉴나 ‘2만원 이상 시 음료 서비스’ 같은 조건으로 객단가를 올려 보세요.")
        if any(k in q for k in ("문자", "sms", "쿠폰", "수신", "발송")):
            usage = ctx["sms"]["usage"]
            quota = f" 이번 달 SMS는 {usage['used']['SMS']}/{usage['limit']['SMS']}건 사용했어요." if usage else ""
            return (f"문자를 받을 수 있는 회원은 {m['sendable']}명(수신거부 {m['opted_out']}명)이에요.{quota} "
                    "야간(21~08시)에는 발송되지 않으니 점심·오후 시간에 보내는 걸 추천해요.")
        if any(k in q for k in ("추천", "어떻게", "뭐", "방법", "마케팅")):
            return "지금 데이터로 드리는 제안이에요.\n\n" + "\n".join(f"{i}. {r['title']} — {r['action']}" for i, r in enumerate(recs[:3], 1))
        return ("질문을 정확히 이해하지 못했어요. 이런 걸 물어보세요: ‘휴면 고객 어떻게 되찾을까?’, ‘인기 메뉴가 뭐야?’, "
                "‘언제 손님이 많아?’, ‘문자 언제 보내면 좋아?’")


class ClaudeClient:
    """TODO(실제 연동): Claude API 호출 지점. 지금은 연결하지 않았다.

    구현 방법: anthropic SDK 로 messages.create(system=context_to_text(ctx) 포함 프롬프트,
    messages=history + [질문]) 를 호출해 텍스트를 돌려준다. API 키는 환경 변수로 받고 화면에 노출하지 않는다.
    """

    def reply(self, question: str, ctx: dict, history: list[dict] | None = None) -> str:
        raise NotImplementedError("Claude API 연동은 아직 구현되지 않았습니다.")


def get_client():
    """챗봇 응답기. Claude API 를 붙일 때 여기서 ClaudeClient() 를 돌려주도록 바꾼다."""
    return RuleBasedClient()


GREETING = "안녕하세요 사장님! 매장 데이터를 보고 마케팅 방법을 같이 고민해 드릴게요. 무엇이 궁금하세요?"


# ---------------------------------------------------------------------------
# AI 문자 생성: 키워드 → 수신 등급 → 문구
# ---------------------------------------------------------------------------
# 발송 API 는 '등급'으로 수신자를 정하므로(수신동의·야간·한도 검사는 서버 몫) 키워드도 등급 집합으로 푼다.
# 복합 키워드는 등급 집합의 교집합이고, 교집합이 비는 조합은 만들지 않는다.
KEYWORD_GRADES = {
    "날씨": ["신규", "재방문", "단골", "휴면"],   # 날씨 안내는 전체 동의 회원
    "행사": ["신규", "재방문", "단골", "휴면"],   # 행사 안내도 전체
    "가중치": ["신규", "재방문", "단골"],        # 추천 가중치가 높은 메뉴를 알릴 대상: 최근 온 손님
    "주문": ["신규", "재방문", "단골"],          # 최근 주문한 손님(휴면 제외)
    "휴면": ["휴면"],
    "단골": ["단골"],
}
KEYWORD_ICON = {"날씨": "🌦️", "행사": "🎉", "가중치": "⚖️", "주문": "🧾", "휴면": "💤", "단골": "🎁"}
DEFAULT_WEATHER = "쌀쌀한 날씨"
DEFAULT_EVENT = "이번 주 특별 이벤트"
SMS_PROMPT = (
    "당신은 호프집 사장님을 돕는 문자 카피라이터입니다. 아래 키워드와 매장 정보로 손님에게 보낼 문자 본문 한 개만 쓰세요. "
    "한국어 존댓말, 친근한 톤, 80자 이내, 이모지 없이. (광고) 표기와 수신거부 안내는 시스템이 붙이니 쓰지 마세요. "
    "설명 없이 문구만 출력하세요.")


def external_context() -> tuple[str, str]:
    """(오늘 날씨, 행사) 문구. TODO: 날씨·행사 API 연동 지점 — 연결 전에는 빈 문자열이라 고정 문구가 쓰인다."""
    return "", ""


def keyword_combos(max_size: int = 2) -> list[tuple[str, ...]]:
    """버튼으로 보여줄 키워드 묶음: 단일 키워드 전부 + 수신자가 겹치는 복합 키워드."""
    names = list(KEYWORD_GRADES)
    out = [(k,) for k in names]
    for n in range(2, max_size + 1):
        out += [c for c in combinations(names, n) if keyword_grades(c)]
    return out


def keyword_grades(keywords) -> list[str]:
    """키워드들의 수신 등급 교집합 (등급 순서 유지). 비면 []."""
    sets = [set(KEYWORD_GRADES[k]) for k in keywords]
    common = set.intersection(*sets) if sets else set()
    return [g for g in GRADE_ORDER if g in common]


def keyword_label(keywords) -> str:
    return " + ".join(keywords)


def _facts(keywords, ctx: dict, weather: str, event: str) -> dict:
    mn, o = ctx["menus"], ctx["orders"]
    return {"weather": weather.strip() or DEFAULT_WEATHER, "event": event.strip() or DEFAULT_EVENT,
            "weight_menu": (mn["high_weight"] or ["인기 메뉴"])[0],
            "top_menu": (o["top_items"][0][0] if o["top_items"] else (mn["high_weight"] or ["인기 메뉴"])[0])}


def template_sms(keywords, ctx: dict, weather: str = "", event: str = "") -> str:
    """AI 키가 없을 때 쓰는 문구. 키워드별 한 문장을 이어 붙인다."""
    f = _facts(keywords, ctx, weather, event)
    parts = {
        "날씨": f"{f['weather']}엔 따끈한 안주에 한잔 어때요?",
        "행사": f"{f['event']}를 준비했어요.",
        "가중치": f"요즘 추천 1순위 ‘{f['weight_menu']}’ 드셔보세요.",
        "주문": f"지난 주문 감사해요. ‘{f['top_menu']}’ 또 드시러 오세요.",
        "휴면": "오랜만이에요! 이번 주 방문하시면 안주 10% 할인해 드려요.",
        "단골": "항상 찾아주셔서 감사해요. 방문 시 음료 1잔을 서비스로 드려요.",
    }
    return " ".join(parts[k] for k in keywords)


def _ask_claude(keywords, ctx: dict, weather: str, event: str, api_key: str) -> str:
    f = _facts(keywords, ctx, weather, event)
    user = (f"키워드: {', '.join(keywords)}\n오늘 날씨: {f['weather']}\n행사: {f['event']}\n"
            f"추천 가중치 높은 메뉴: {', '.join(ctx['menus']['high_weight'])}\n매장 현황: {context_to_text(ctx)}")
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=15,
                   headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                   json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5"), "max_tokens": 300,
                         "system": SMS_PROMPT, "messages": [{"role": "user", "content": user}]})
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text").strip()


def generate_sms(keywords, ctx: dict, weather: str = "", event: str = "") -> tuple[str, str]:
    """(문구, 출처) 를 돌려준다. 출처는 'ai' 또는 'template'. ANTHROPIC_API_KEY 가 없거나 호출이 실패하면 템플릿."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        try:
            text = _ask_claude(keywords, ctx, weather, event, key)
            if text:
                return text, "ai"
        except (httpx.HTTPError, KeyError, ValueError):
            pass
    return template_sms(keywords, ctx, weather, event), "template"


CANDIDATE_ORDER = [("휴면",), ("단골",), ("주문", "단골"), ("날씨", "주문"), ("행사",), ("가중치", "주문"), ("날씨", "행사"), ("주문",)]


def suggest_candidates(ctx: dict, weather: str = "", event: str = "", n: int = 5) -> list[dict]:
    """AI 문자 생성 버튼용 후보 n개. 각 후보 = 키워드 + 수신 등급 + 문구. 수신 가능 회원이 없는 등급 조합은 건너뛴다."""
    pool = ctx["members"]["pool_by_grade"]
    picks = [kw for kw in CANDIDATE_ORDER
             if any(pool.get(g, 0) for g in keyword_grades(kw))][:n]

    def make(kw):
        body, source = generate_sms(kw, ctx, weather, event)
        return {"keywords": list(kw), "grades": keyword_grades(kw), "body": body, "source": source}
    with ThreadPoolExecutor(max_workers=max(1, len(picks))) as ex:
        return list(ex.map(make, picks))
