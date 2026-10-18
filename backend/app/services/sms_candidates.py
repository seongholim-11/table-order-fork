"""AI 문자 후보를 만든다 (admin/marketing_ai.py 의 화면용 로직을 서버로 옮긴 것).

흐름: 매장 데이터 요약(수신 가능 회원 수·추천 가중치 높은 메뉴·인기 메뉴) → 키워드 조합 고르기 → 문구 만들기.
문구는 제미나이(GEMINI_API_KEY)로 만들고, 키가 없거나 호출이 실패하면 템플릿으로 대신한다(source 로 구분).
"""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.core.settings import Settings
from app.services.external_info import ExternalInfoService
from app.services.grades import GRADES, grade_of
from app.services.sms import SmsService

# 키워드마다 문자를 받을 등급. 발송 API 가 '등급'으로 수신자를 정하므로 키워드도 등급으로 푼다.
# 복합 키워드는 등급의 교집합이고, 비는 조합은 만들지 않는다.
KEYWORD_GRADES = {
    "날씨": ["신규", "재방문", "단골", "휴면"],
    "행사": ["신규", "재방문", "단골", "휴면"],
    "가중치": ["신규", "재방문", "단골"],  # 추천 가중치가 높은 메뉴를 알릴 대상: 최근 온 손님
    "주문": ["신규", "재방문", "단골"],    # 최근 주문한 손님(휴면 제외)
    "휴면": ["휴면"],
    "단골": ["단골"],
}
# 화면에 먼저 보여 줄 키워드 조합 순서. 수신할 회원이 있는 조합만 앞에서부터 n개 쓴다.
CANDIDATE_ORDER = [("휴면",), ("단골",), ("주문", "단골"), ("날씨", "주문"), ("행사",), ("가중치", "주문"), ("날씨", "행사"), ("주문",)]
DEFAULT_WEATHER = "쌀쌀한 날씨"
DEFAULT_EVENT = "이번 주 특별 이벤트"
MENU_SEED = Path(__file__).resolve().parent.parent / "seed" / "menu.json"  # 메뉴 저장소가 비어 있을 때 쓰는 기본 메뉴
PROMPT = (
    "당신은 호프집 사장님을 돕는 문자 카피라이터입니다. 손님 입장에서 '오늘 이 가게에 가고 싶다'는 마음이 들게 "
    "문자 본문 한 개만 쓰세요. 키워드마다 손님이 끌릴 포인트를 하나씩만 담고, 키워드에 없는 정보는 넣지 마세요. "
    "행사는 주어진 행사명 하나만 따옴표 그대로 짧게 말하고, 메뉴는 주어진 이름과 짧은 특징으로 말하세요. "
    "혜택은 주어진 것만 쓰고 가격·할인을 지어내지 마세요. "
    "2~3문장, 90자 이내, 한국어 존댓말, 친근하고 자연스러운 말투, 이모지 없이. '한잔', '어때요' 같은 말을 반복하지 마세요. "
    "(광고) 표기와 수신거부 안내는 시스템이 붙이니 쓰지 마세요. 설명 없이 문구만 출력하세요.")
# 휴면·단골 키워드에서 주는 혜택. 템플릿과 AI 가 같은 혜택만 말하도록 한곳에 둔다.
OFFERS = {"휴면": "이번 주 방문하시면 안주 10% 할인", "단골": "방문하시면 음료 1잔 서비스"}


def keyword_grades(keywords) -> list[str]:
    """키워드들의 수신 등급 교집합 (GRADES 순서 유지). 비면 []."""
    common = set.intersection(*(set(KEYWORD_GRADES[k]) for k in keywords)) if keywords else set()
    return [g for g in GRADES if g in common]


class SmsCandidateService:
    def __init__(self, settings: Settings, sms: SmsService, shop, external: ExternalInfoService):
        self.s, self.sms, self.shop, self.external = settings, sms, shop, external

    # ---- 매장 데이터 요약 ----
    def summary(self) -> dict:
        """문구에 쓸 사실만 모은다: 등급별 수신 가능 회원 수, 추천 가중치 높은 메뉴, 인기 메뉴."""
        today = self.sms.clock().date()
        # 후보별 고객 수와 실제 발송 대상이 같은 등급 정책을 사용한다.
        rule = self.sms.grade_rule()
        pool = Counter(grade_of(m, today, **rule) for m in self.sms.targets(GRADES))
        try:  # 메뉴 저장소가 아직 뼈대(NotImplementedError)면 기본 메뉴 파일(seed/menu.json)을 쓴다
            menus = self.shop.menus()
        except NotImplementedError:
            menus = json.loads(MENU_SEED.read_text(encoding="utf-8"))
        menus = [m for m in menus if not m.get("soldout")]
        # 추천 가중치가 높은 순(같으면 BEST 태그 먼저)으로 3개: 문구에 이름·가격·설명을 구체적으로 쓰기 위해 통째로 둔다
        best = sorted(menus, key=lambda m: (m.get("weight", 0), "BEST" in m.get("tags", [])), reverse=True)[:3]
        high_weight = [{"name": m["name"], "price": m.get("price"), "desc": m.get("desc", "")} for m in best]
        try:
            sold = Counter()
            for order in self.shop.orders():
                for line in order["lines"]:
                    sold[line["name"]] += line["qty"]
            top_items = [name for name, _ in sold.most_common(3)]
        except NotImplementedError:
            top_items = []
        return {"pool": dict(pool), "high_weight": high_weight, "top_items": top_items}

    # ---- 문구 만들기 ----
    def _facts(self, summary: dict, info: dict) -> dict:
        weight_menu = self._short_name(summary["high_weight"][0]["name"]) if summary["high_weight"] else "인기 메뉴"
        # 가격은 문자에 쓰지 않으므로 빼고, 설명은 첫 구절만 짧게 쓴다
        detail = "; ".join(f"{self._short_name(m['name'])} - {self._short_desc(m['desc'])}" if m["desc"]
                           else self._short_name(m["name"]) for m in summary["high_weight"])
        return {"weight_detail": detail or weight_menu, "weather": info["weather_text"].strip() or DEFAULT_WEATHER,
                "event": info["event_text"].strip() or DEFAULT_EVENT,
                "weight_menu": weight_menu,
                "weight_desc": self._short_desc(summary["high_weight"][0]["desc"]) if summary["high_weight"] else "",
                "top_menu": (summary["top_items"] or [""])[0]}  # 주문 기록이 없으면 빈 값

    @staticmethod
    def _short_name(name: str) -> str:
        """메뉴 이름에서 괄호 설명을 뺀다: "역전 옛날통닭 (한 마리·후라이드)" → "역전 옛날통닭"."""
        return name.split("(")[0].strip() or name

    @staticmethod
    def _short_desc(desc: str) -> str:
        """메뉴 설명을 짧게: 20자 이하면 그대로, 길면 첫 구절(쉼표·마침표 앞)만 최대 20자."""
        desc = desc.strip().rstrip(".")
        return desc if len(desc) <= 20 else desc.replace(".", ",").split(",")[0].strip()[:20]

    @staticmethod
    def _josa(word: str, with_final: str, without_final: str) -> str:
        """앞 글자에 받침이 있으면 with_final(은·이에요), 없으면 without_final(는·예요)을 붙인다."""
        last = word.rstrip("’'\" )")[-1:] if word else ""
        has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
        return word + (with_final if has_final else without_final)

    def template(self, keywords, f: dict) -> str:
        """AI 를 못 쓸 때의 문구: 키워드마다 손님이 끌릴 포인트를 한 문장씩, 겹치는 말 없이 이어 붙인다."""
        parts = {
            "날씨": f"오늘은 {f['weather']}, 시원한 생맥주가 딱 어울리는 날이에요.",
            "행사": f"근처 {f['event']} 보고 오시는 길에 들러 보세요.",
            # 예: "요즘 추천 메뉴 ‘역전 옛날통닭’은 겉은 바삭, 속은 촉촉한 가마솥 통닭이에요."
            "가중치": (f"요즘 추천 메뉴 {self._josa('‘' + f['weight_menu'] + '’', '은', '는')} "
                     f"{self._josa(f['weight_desc'], '이에요', '예요')}." if f["weight_desc"]
                     else f"요즘 추천 메뉴는 {self._josa('‘' + f['weight_menu'] + '’', '이에요', '예요')}."),
            # 주문 기록이 있으면 그 메뉴를, 없거나 추천 메뉴와 겹치면 메뉴 없이 감사 인사만
            "주문": (f"지난번 드신 ‘{f['top_menu']}’, 생각나실 때 또 들러 주세요."
                   if f["top_menu"] and f["top_menu"] != f["weight_menu"]
                   else "지난번 방문 감사했어요. 생각나실 때 또 들러 주세요."),
            "휴면": f"오랜만에 뵙고 싶어요! {OFFERS['휴면']}해 드려요.",
            "단골": f"늘 찾아 주셔서 감사해요. {OFFERS['단골']}로 드려요.",
        }
        text = " ".join(parts[k] for k in keywords)
        # 방문을 권하는 문장(주문·휴면·단골)이 없으면 마지막에 한 번만 초대 문장을 붙인다
        if not {"주문", "휴면", "단골"} & set(keywords):
            text += f" {self.s.store_name} {self.s.store_branch}에서 기다릴게요."
        return text

    def _ask_gemini(self, keywords, f: dict) -> str:
        """제미나이에 문구 한 개를 요청한다. 키워드에 해당하는 사실만 넘겨 문구가 산만해지지 않게 한다. 실패하면 예외."""
        facts = {
            "날씨": f"오늘 날씨: {f['weather']}",
            "행사": f"근처 행사: {f['event']}",
            "가중치": f"추천 메뉴(이름 - 특징): {f['weight_detail']}",
            "주문": (f"손님이 전에 많이 드신 메뉴: {f['top_menu']}" if f["top_menu"]
                   else "전에 방문한 적 있는 손님 (드신 메뉴 정보 없음)"),
            "휴면": f"오랜만에 오는 손님 혜택: {OFFERS['휴면']}",
            "단골": f"단골 손님 혜택: {OFFERS['단골']}",
        }
        user = (f"매장: {self.s.store_name} {self.s.store_branch}\n키워드: {', '.join(keywords)}\n"
                + "\n".join(facts[k] for k in keywords))
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent",
            timeout=15, headers={"x-goog-api-key": self.s.gemini_api_key},
            json={"systemInstruction": {"parts": [{"text": PROMPT}]}, "contents": [{"parts": [{"text": user}]}]})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate(self, keywords, f: dict) -> tuple[str, str]:
        """(문구, 출처). 출처는 'ai' 또는 'template'. 키가 없거나 호출이 실패하면 템플릿."""
        if self.s.gemini_api_key:
            try:
                text = self._ask_gemini(keywords, f)
                if text:
                    return text, "ai"
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                pass
        return self.template(keywords, f), "template"

    # ---- 후보 목록 ----
    def candidates(self, n: int = 5) -> list[dict]:
        """후보 최대 n개: [{keywords, grades, body, source}]. 수신 가능 회원이 없는 등급 조합은 뺀다."""
        summary, info = self.summary(), self.external.today()
        f = self._facts(summary, info)
        # 오늘 날씨·행사 정보가 없으면 그 키워드가 든 조합은 뺀다 (없는 정보를 지어낸 듯한 문구를 막는다)
        missing = {k for k, v in (("날씨", info["weather_text"]), ("행사", info["event_text"])) if not v.strip()}
        picks = [kw for kw in CANDIDATE_ORDER
                 if not missing & set(kw) and any(summary["pool"].get(g, 0) for g in keyword_grades(kw))][:n]

        def make(kw):
            body, source = self.generate(kw, f)
            return {"keywords": list(kw), "grades": keyword_grades(kw), "body": body, "source": source}
        if not picks:
            return []
        with ThreadPoolExecutor(max_workers=len(picks)) as ex:  # 후보를 동시에 만들어 AI 호출 시간을 줄인다
            return list(ex.map(make, picks))
