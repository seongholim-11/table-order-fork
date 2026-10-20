"""오늘의 외부 정보(날씨·주변 행사) 문구를 만든다. 결과는 DB에 하루 한 번만 저장해 재사용한다.

- 날씨: Open-Meteo (인증키 없는 무료 API). 매장 좌표의 현재 날씨를 "맑은 18도 날씨"처럼 한 줄로 만든다.
- 행사: 서울 열린데이터광장 '서울시 문화행사 정보'(SEOUL_OPENAPI_KEY 필요). 매장이 있는 자치구에서 오늘 열리는 행사만 쓴다.
외부 호출이 실패해도 예외를 밖으로 내보내지 않고 빈 문자열을 돌려준다(문자 후보 생성이 멈추지 않게).
"""

import re
from datetime import datetime

import httpx

from app.core.settings import Settings
from app.services.grades import KST
from app.stores.external_context import ExternalContextStore

# Open-Meteo 날씨 코드 → "맑은" 같은 꾸밈말. 코드표에 없으면 "날씨"만 쓴다.
WEATHER_WORDS = {0: "맑은", 1: "대체로 맑은", 2: "구름 많은", 3: "흐린", 45: "안개 낀", 48: "안개 낀",
                 51: "이슬비 오는", 53: "이슬비 오는", 55: "이슬비 오는", 61: "비 오는", 63: "비 오는", 65: "비 오는",
                 66: "비 오는", 67: "비 오는", 71: "눈 오는", 73: "눈 오는", 75: "눈 오는", 77: "눈 오는",
                 80: "소나기 오는", 81: "소나기 오는", 82: "소나기 오는", 85: "눈 오는", 86: "눈 오는",
                 95: "천둥 치는", 96: "천둥 치는", 99: "천둥 치는"}
EVENT_URL = "http://openapi.seoul.go.kr:8088/{key}/json/culturalEventInfo/1/200/%20/%20/{day}"


def weather_type(text: str) -> str | None:
    """"맑은 18도 날씨" 같은 문구를 손님 추천이 쓰는 날씨 코드(sunny/cloudy/rain/snow/hot)로 바꾼다. 모르면 None."""
    degree = re.search(r"(-?\d+)도", text or "")
    if degree and int(degree.group(1)) >= 30:
        return "hot"
    if any(word in text for word in ("비", "소나기", "천둥")):  # "이슬비 오는" 도 '비'가 들어 있다
        return "rain"
    if "눈" in text:
        return "snow"
    if any(word in text for word in ("흐린", "구름", "안개")):
        return "cloudy"
    return "sunny" if "맑" in text else None


class ExternalInfoService:
    def __init__(self, settings: Settings, store: ExternalContextStore, clock=None):
        self.s, self.store = settings, store
        self.clock = clock or (lambda: datetime.now(KST))
        self.notes = {"weather": "", "event": ""}  # 값이 비었을 때의 이유 (today() 가 호출마다 새로 채운다)

    def today(self) -> dict:
        """오늘(KST) 날씨·행사 문구. 저장된 게 있으면 그대로 쓰고, 비어 있는 것만 외부 API로 다시 채워 저장한다.

        weather_note / event_note 는 값이 비었을 때 그 이유(화면에 보여 주는 용도)이고, 값이 있으면 ''이다."""
        day = self.clock().strftime("%Y-%m-%d")
        saved = self.store.get(day) or {"weather_text": "", "event_text": ""}
        weather, event = saved["weather_text"], saved["event_text"]
        self.notes = {"weather": "", "event": ""}
        # 한쪽만 성공해 저장된 날에도 빈 쪽은 다시 시도한다(예전에는 한쪽만 있으면 하루 종일 다시 부르지 않았다)
        if not weather:
            weather = self.fetch_weather()
        if not event:
            event = self.fetch_events(day)
        if (weather, event) != (saved["weather_text"], saved["event_text"]):  # 새로 얻은 값이 있을 때만 저장
            self.store.save(day, weather, event)
        weather_note = "" if weather else (self.notes["weather"] or "날씨 정보를 가져오지 못했습니다")
        event_note = "" if event else (self.notes["event"] or f"오늘 {self.s.store_gu} 행사가 없습니다")
        return {"day": day, "weather_text": weather, "event_text": event,
                "weather_note": weather_note, "event_note": event_note}

    def today_weather(self) -> str:
        """오늘 날씨 문구만. 손님 화면용이라 행사 조회(느린 외부 호출)는 하지 않는다. 저장된 값이 있으면 그대로 쓴다."""
        day = self.clock().strftime("%Y-%m-%d")
        saved = self.store.get(day) or {"weather_text": "", "event_text": ""}
        if saved["weather_text"]:
            return saved["weather_text"]
        weather = self.fetch_weather()
        if weather:  # 가져왔을 때만 저장한다(행사 문구는 그대로 둔다)
            self.store.save(day, weather, saved["event_text"])
        return weather

    def fetch_weather(self) -> str:
        """매장 위치의 현재 날씨 한 줄. 실패하면 ''(이유는 self.notes 에 남긴다)."""
        try:
            r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=5, params={
                "latitude": self.s.store_lat, "longitude": self.s.store_lon,
                "current": "temperature_2m,weather_code", "timezone": "Asia/Seoul"})
            r.raise_for_status()
            cur = r.json()["current"]
            word = WEATHER_WORDS.get(int(cur["weather_code"]), "")
            return f"{word} {round(cur['temperature_2m'])}도 날씨".strip()
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            self.notes["weather"] = f"날씨 조회 실패(Open-Meteo: {type(e).__name__})"
            return ""

    def fetch_events(self, day: str) -> str:
        """매장 자치구에서 오늘 열리는 문화행사 하나를 짧은 한 줄로. 키가 없거나 실패하면 ''(이유는 self.notes)."""
        if not self.s.seoul_openapi_key:
            self.notes["event"] = "서버에 SEOUL_OPENAPI_KEY 가 설정되지 않아 행사를 조회하지 않았습니다"
            return ""
        try:
            r = httpx.get(EVENT_URL.format(key=self.s.seoul_openapi_key, day=day), timeout=8)
            r.raise_for_status()
            rows = r.json()["culturalEventInfo"]["row"]
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            self.notes["event"] = f"행사 조회 실패(서울 열린데이터광장: {type(e).__name__}) - 인증키를 확인하세요"
            return ""
        # 요청 날짜 필터를 믿지 않고 한 번 더 거른다: 우리 자치구 + 오늘이 시작일~종료일 사이
        today = [row for row in rows
                 if row.get("GUNAME") == self.s.store_gu
                 and str(row.get("STRTDATE", ""))[:10] <= day <= str(row.get("END_DATE", ""))[:10]]
        if not today:
            self.notes["event"] = f"오늘 {self.s.store_gu}에서 열리는 행사가 없습니다"
            return ""
        # 문자에는 행사 하나만 짧게 넣는다: 이름을 다듬었을 때 가장 짧은(읽기 쉬운) 행사를 고른다
        row = min(today, key=lambda r: len(self._short_title(r.get("TITLE", ""))))
        return self._event_label(row, day)

    @staticmethod
    def _short_title(title: str) -> str:
        """행사명을 문자에 넣기 좋게 줄인다.
        "[마포문화재단] 2026 [인디스커버리 : FESTA] TRACK 02" → "인디스커버리 FESTA TRACK 02",
        "포개진 지도 - 미시적이지만 거시적인 풍경" → "포개진 지도"."""
        text = re.sub(r"^\s*[\[(][^\])]*[\])]\s*", "", title)  # 맨 앞 [주최 기관] 은 뺀다
        text = re.sub(r"[\[\]()]", " ", text)                 # 나머지 괄호는 기호만 지운다
        text = re.split(r"\s+-\s+|\s*[|~]\s*", text)[0]       # " - " 뒤 부제는 버린다
        text = re.sub(r"\s*:\s*", " ", text)
        text = re.sub(r"^(19|20)\d{2}\s+", "", text.strip())  # 앞의 연도("2026 ")는 뺀다
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= 24 else text[:24].rstrip() + "…"

    @classmethod
    def _event_label(cls, row: dict, day: str) -> str:
        """행사 한 건을 "장소의 '행사명'(10/23까지)" 로 만든다. 장소가 없으면 빼고, 오늘 끝나면 "오늘까지"."""
        end = str(row.get("END_DATE") or "")[:10]
        until = "오늘까지" if end == day else (f"{int(end[5:7])}/{int(end[8:10])}까지" if len(end) == 10 else "")
        place = str(row.get("PLACE") or "").strip()
        return (f"{place}의 " if place else "") + f"'{cls._short_title(row['TITLE'])}'" + (f"({until})" if until else "")
