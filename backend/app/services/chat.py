"""관리자 AI 챗봇: DB 데이터를 문장으로 요약해 프롬프트에 붙이고 제미나이에 질문한다 (RAG·MCP 없음).

요약에 답이 없는 질문(임의 기간·특정 메뉴 등)은 제미나이가 아래 조회 함수(TOOLS) 중 하나를 골라 부르게 한다.
SQL 과 계산은 항상 서버가 하고, 제미나이는 "어떤 함수를 어떤 인자로 부를지"만 정한다.
"""

from collections import Counter
from datetime import date, datetime, timedelta

import httpx

from app.core.settings import Settings
from app.services import stats as stats_service
from app.services.grades import GRADES, KST, grade_of

GREETING = "안녕하세요 사장님! 매장 데이터를 보고 궁금한 점에 답해 드릴게요. 예) 저번주 총 매출 알려줘"
NO_KEY_REPLY = "AI 챗봇을 쓰려면 서버에 GEMINI_API_KEY 설정이 필요해요. 관리자에게 설정을 요청해 주세요."
HISTORY_LIMIT = 20  # 제미나이에 다시 보내는 이전 대화 개수 (무료 한도·토큰을 아끼려고 최근 것만)
MAX_TOOL_ROUNDS = 4  # 한 질문에서 조회 함수를 부를 수 있는 최대 횟수 (무한 반복·무료 한도 소진 방지)

PROMPT = (
    "당신은 호프집 사장님을 돕는 매장 데이터 도우미입니다. 한국어로 짧고 친절하게 답하세요.\n"
    "답은 아래 '매장 데이터'와 조회 함수의 결과에 있는 숫자와 사실만 근거로 하세요. 금액은 원 단위로 쉼표를 붙여 말하세요.\n"
    "1) '매장 데이터'에 답이 있으면 그대로 답하세요. 질문의 '오늘·어제·이번 주·저번 주(지난주)·이번 달·지난달'은 "
    "같은 이름 항목을 보세요.\n"
    "2) 없으면 조회 함수를 부르세요. 날짜는 오늘 날짜를 기준으로 YYYY-MM-DD 로 직접 계산해 넘기세요.\n"
    "3) 함수로도 알 수 없는 내용(매출·주문·메뉴 판매 외의 데이터)은 추측하지 말고 '아직 알 수 없어요'라고 답하세요. "
    "숫자를 직접 계산하지 말고, 합계·평균은 함수 결과를 그대로 쓰세요."
)

_DATE = {"type": "STRING", "description": "YYYY-MM-DD"}
# 제미나이에 알려 주는 조회 함수 목록(이름·설명·인자). 실제 계산은 ChatService.run_tool 이 한다.
TOOLS = [{"functionDeclarations": [
    {"name": "sales_between",
     "description": "기간(양 끝 날짜 포함)의 총 매출, 주문 건수, 평균 주문 금액을 조회한다.",
     "parameters": {"type": "OBJECT", "properties": {"start_date": _DATE, "end_date": _DATE},
                    "required": ["start_date", "end_date"]}},
    {"name": "sales_breakdown",
     "description": "기간의 매출을 일별(day)·요일별(weekday)·시간대별(hour)로 나눠 조회한다. 예: 화요일 매출, 가장 바쁜 시간.",
     "parameters": {"type": "OBJECT", "properties": {
         "start_date": _DATE, "end_date": _DATE,
         "by": {"type": "STRING", "enum": ["day", "weekday", "hour"]}},
         "required": ["start_date", "end_date", "by"]}},
    {"name": "menu_sold",
     "description": "특정 메뉴가 기간에 몇 개 팔렸는지 조회한다. 메뉴 이름의 일부만 맞아도 찾는다.",
     "parameters": {"type": "OBJECT", "properties": {"menu_name": {"type": "STRING"},
                                                     "start_date": _DATE, "end_date": _DATE},
                    "required": ["menu_name", "start_date", "end_date"]}},
    {"name": "top_menus",
     "description": "기간에 많이 팔린 메뉴 순위를 조회한다.",
     "parameters": {"type": "OBJECT", "properties": {"start_date": _DATE, "end_date": _DATE,
                                                     "limit": {"type": "INTEGER", "description": "기본 5, 최대 20"}},
                    "required": ["start_date", "end_date"]}},
]}]


class ChatUnavailable(Exception):
    """제미나이 호출이 실패했다(한도 초과·네트워크 오류 등). 라우터가 502 로 바꾼다."""


class ChatService:
    def __init__(self, settings: Settings, stats_store, members):
        self.s = settings
        self.stats_store = stats_store
        self.members = members

    # ---- 매장 데이터 요약 ----
    @staticmethod
    def _period(orders: list[dict], start: date, end: date) -> str:
        """start~end(양 끝 포함) 기간의 매출·주문 건수를 한 줄 문장으로 만든다."""
        picked = [o for o in orders if start <= o["day"] <= end]
        if not picked:
            return "주문 없음(0원)"
        return f"매출 {sum(o['total'] for o in picked):,}원, 주문 {len(picked)}건"

    def _orders(self) -> list[dict]:
        """주문마다 한국 날짜(day)·요일·시(hour)를 붙여 둔다. 시각 문자열을 미리 바꿔 두면 기간 비교가 쉽다."""
        rows = []
        for o in self.stats_store.sales_orders():
            at = stats_service.order_time(o["ts"])
            rows.append({**o, "day": at.date(), "hour": at.hour})
        return rows

    def summary(self, today: date) -> str:
        """기간별 매출·요일·시간대·메뉴·회원 등급을 프롬프트에 넣을 문장으로 만든다. 합계는 항상 서버가 계산한다."""
        orders = self._orders()
        this_monday = today - timedelta(days=today.weekday())  # 이번 주 월요일
        last_monday = this_monday - timedelta(days=7)
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        total = sum(o["total"] for o in orders)
        lines = [
            f"오늘은 {today:%Y-%m-%d}({stats_service.WEEKDAYS[today.weekday()]}요일)입니다.",
            f"- 오늘: {self._period(orders, today, today)}",
            f"- 어제: {self._period(orders, today - timedelta(days=1), today - timedelta(days=1))}",
            f"- 이번 주({this_monday:%m/%d}~오늘): {self._period(orders, this_monday, today)}",
            f"- 저번 주(지난주, {last_monday:%m/%d}~{this_monday - timedelta(days=1):%m/%d}): "
            f"{self._period(orders, last_monday, this_monday - timedelta(days=1))}",
            f"- 이번 달: {self._period(orders, month_start, today)}",
            f"- 지난달: {self._period(orders, last_month_end.replace(day=1), last_month_end)}",
            f"- 전체 누적: 매출 {total:,}원, 주문 {len(orders)}건, 평균 주문 금액 {total // len(orders) if orders else 0:,}원",
        ]
        # 최근 7일 일별 매출 (날짜마다 한 줄이 아니라 한 문장으로 묶어 프롬프트를 짧게 유지한다)
        daily = [f"{d:%m/%d}({stats_service.WEEKDAYS[d.weekday()]}) {self._period(orders, d, d)}"
                 for d in (today - timedelta(days=n) for n in range(6, -1, -1))]
        lines.append("- 최근 7일 일별: " + " / ".join(daily))
        weekday, hourly = Counter(), Counter()
        for o in orders:
            weekday[o["day"].weekday()] += o["total"]
            hourly[o["hour"]] += o["total"]
        lines.append("- 요일별 누적 매출: " + ", ".join(
            f"{name} {weekday[i]:,}원" for i, name in enumerate(stats_service.WEEKDAYS)))
        lines.append("- 시간대별 누적 매출(매출 상위 3): " + (", ".join(
            f"{h:02d}시 {v:,}원" for h, v in hourly.most_common(3)) or "기록 없음"))
        sold = Counter()
        for row in self.stats_store.menu_sales():
            sold[row["name"]] += row["qty"]
        top = ", ".join(f"{name} {qty}개" for name, qty in sold.most_common(10))
        lines.append(f"- 인기 메뉴(누적 판매 수량 상위 10): {top or '판매 기록 없음'}")
        soldout = [m["name"] for m in self.stats_store.menu_stock() if m["is_soldout"]]
        lines.append(f"- 현재 품절 메뉴: {', '.join(soldout) or '없음'}")
        members = self.members.all()
        rule = dict(repeat=self.s.grade_repeat_visits, regular=self.s.grade_regular_visits,
                    dormant=self.s.grade_dormant_days)
        grades = Counter(grade_of(m, today, **rule) for m in members)
        lines.append(f"- 전체 회원 {len(members)}명 (" + ", ".join(f"{g} {grades[g]}명" for g in GRADES) + ")")
        return "\n".join(lines)

    # ---- 조회 함수 (제미나이가 골라 부른다) ----
    @staticmethod
    def _day(value) -> date:
        """제미나이가 넘긴 날짜 문자열을 date 로 바꾼다. 형식이 틀리면 ValueError."""
        return date.fromisoformat(str(value))

    def run_tool(self, name: str, args: dict) -> dict:
        """조회 함수 한 개를 실행해 결과 dict 를 돌려준다. 인자가 잘못되면 {"error": ...} 를 줘서 제미나이가 고치게 한다."""
        try:
            start, end = self._day(args.get("start_date")), self._day(args.get("end_date"))
        except ValueError:
            return {"error": "날짜는 YYYY-MM-DD 형식이어야 합니다."}
        if end < start:
            return {"error": "end_date 는 start_date 보다 같거나 늦어야 합니다."}
        if name in ("sales_between", "sales_breakdown"):
            picked = [o for o in self._orders() if start <= o["day"] <= end]
            revenue = sum(o["total"] for o in picked)
            if name == "sales_between":
                return {"revenue": revenue, "orders": len(picked), "avg_order": revenue // len(picked) if picked else 0}
            by = args.get("by")
            if by not in ("day", "weekday", "hour"):
                return {"error": "by 는 day, weekday, hour 중 하나여야 합니다."}
            groups = {}
            for o in picked:
                key = {"day": f"{o['day']:%Y-%m-%d}", "weekday": stats_service.WEEKDAYS[o["day"].weekday()],
                       "hour": f"{o['hour']:02d}시"}[by]
                g = groups.setdefault(key, {"revenue": 0, "orders": 0})
                g["revenue"] += o["total"]
                g["orders"] += 1
            return {"by": by, "revenue_total": revenue, "groups": dict(sorted(groups.items()))}
        sold = Counter()
        keyword = str(args.get("menu_name") or "").strip()
        for row in self.stats_store.dated_menu_sales():
            if not start <= stats_service.order_date(row["ts"]) <= end:
                continue
            if name == "top_menus" or (keyword and keyword in row["name"]):
                sold[row["name"]] += row["qty"]
        if name == "menu_sold":
            if not keyword:
                return {"error": "menu_name 이 필요합니다."}
            return {"menu_name": keyword, "total_qty": sum(sold.values()), "matched_menus": dict(sold)}
        if name == "top_menus":
            try:
                limit = min(max(int(args.get("limit") or 5), 1), 20)
            except (TypeError, ValueError):
                limit = 5
            return {"top": [{"name": n, "qty": q} for n, q in sold.most_common(limit)]}
        return {"error": f"알 수 없는 함수입니다: {name}"}

    # ---- 제미나이 ----
    def _call(self, system: str, contents: list[dict]) -> dict:
        """제미나이를 한 번 부르고 답변 content(parts 목록)를 돌려준다. 실패하면 예외."""
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent",
            timeout=15, headers={"x-goog-api-key": self.s.gemini_api_key},
            json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "tools": TOOLS})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]

    def _ask_gemini(self, system: str, history: list[dict], question: str) -> str:
        """이전 대화 + 새 질문을 보내 답변 텍스트를 받는다. 제미나이가 조회 함수를 부르면 실행해 결과를 돌려주고 다시 묻는다."""
        recent = history[-HISTORY_LIMIT:]
        while recent and recent[0]["role"] != "user":  # 제미나이는 user 메시지로 시작해야 하므로 첫 인사 같은 앞쪽 assistant 는 뺀다
            recent = recent[1:]
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in recent]
        contents.append({"role": "user", "parts": [{"text": question}]})
        for _ in range(MAX_TOOL_ROUNDS + 1):
            reply = self._call(system, contents)
            parts = reply.get("parts", [])
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not calls:
                return "".join(p.get("text", "") for p in parts).strip()
            # 함수 호출 요청을 대화에 그대로 남기고, 서버가 실행한 결과를 functionResponse 로 붙여 다시 보낸다.
            contents.append({"role": "model", "parts": parts})
            contents.append({"role": "user", "parts": [
                {"functionResponse": {"name": c["name"], "response": self.run_tool(c["name"], c.get("args") or {})}}
                for c in calls]})
        raise ValueError("조회 함수 호출이 너무 많습니다.")

    def answer(self, history: list[dict], question: str, today: date | None = None) -> str:
        """질문에 대한 답변. 키가 없으면 안내 문구를 돌려주고, 호출이 실패하면 ChatUnavailable."""
        if not self.s.gemini_api_key:
            return NO_KEY_REPLY
        today = today or datetime.now(KST).date()
        system = f"{PROMPT}\n\n[매장 데이터]\n{self.summary(today)}"
        try:
            text = self._ask_gemini(system, history, question)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # 무료 한도 초과: 재시도하지 않고 안내만 한다
                raise ChatUnavailable("AI 호출 한도를 넘었어요. 잠시 후 다시 시도해 주세요.") from e
            raise ChatUnavailable("AI 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.") from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise ChatUnavailable("AI 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.") from e
        if not text:
            raise ChatUnavailable("AI 답변이 비어 있어요. 다시 질문해 주세요.")
        return text
