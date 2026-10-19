"""user 페이지가 쓰는 모든 '화면용 데이터'의 단일 출입구.

화면 코드(app.py)는 데이터가 더미인지 서버(API)인지 모른다. 여기서만 정한다.

데이터 소스 전환: 환경 변수 DATA_SOURCE
  dummy : 코드 안의 더미 데이터만 쓴다 (서버 불필요)
  api   : 서버(API_URL)에서만 가져온다. 서버가 안 닿으면 오류 화면
  auto  : 서버가 닿으면 API, 안 닿으면 더미 (기본값. 시연·개발용)

새 데이터를 API로 바꾸려면 (3곳만 보면 된다)
  1) ENDPOINTS 에 경로를 적고
  2) ApiRepository.load_content() 에 가져오는 줄을 추가하고
  3) 서버 응답이 더미와 같은 모양이 되게 한다 (더미 파일이 곧 응답 명세다).
     더미: menu_data.py, ai_quiz_data.py, recommendation_data.py
"""
import copy
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

import server
from shared import api

# 서버 경로 한 곳 정리. 서버 주소(API_URL)는 shared/api.py 에서 정한다.
ENDPOINTS = {
    "store": "/api/v1/store",                    # {name, branch, tables}
    "menus": "/api/menus",                    # [메뉴...]
    "content": "/api/content/categories",     # [카테고리...] (묶음 경로 /api/content 는 안 쓰는 값까지 읽어서 느리다)
    "staff_call_items": "/api/v1/staff-call-items",  # ["💧 물", ...]
    "questions": "/api/v1/ai/questions",      # 추천 질문·선택지
    "weather": "/api/v1/weather/current",    # 현재 날씨
    "rules": "/api/v1/ai/recommendation-rules",  # 추천 규칙
    "roulette": "/api/v1/roulette/prizes",    # 관리자 설정과 같은 DB의 룰렛 칸
    "orders": "/api/orders",                  # POST
    "table_orders": "/api/v1/tables/{table_no}/orders",  # GET
    "calls": "/api/v1/staff-calls",           # POST
    "recommendations": "/api/v1/ai/recommendations",  # POST (추천 노출 기록)
    "recommendation_generate": "/api/v1/ai/recommendations/generate",  # POST (제미나이 조합 추천)
}
CONTENT_KEYS = ("categories",)
MODES = ("dummy", "api", "auto")


def dev_test_button_enabled() -> bool:
    """화면 환경변수가 켜져 있을 때만 개발용 DB 테스트 버튼을 보여 준다."""
    return os.getenv("DEV_TEST_BUTTON", "").strip().lower() in {"1", "true", "yes", "on"}


def dev_db_test() -> dict:
    """화면에서 서버를 직접 부르지 않고 개발용 DB 왕복 확인을 요청한다."""
    try:
        return api.post("/api/dev/db-test") or {"result": 0, "reason": "서버가 빈 응답을 반환했습니다."}
    except api.ApiError as exc:
        return {"result": 0, "reason": str(exc.detail)}
    except api.ApiUnavailable:
        return {"result": 0, "reason": "서버에 연결할 수 없습니다."}


class ContentUnavailable(Exception):
    """api 모드에서 서버 데이터를 가져오지 못함."""


@dataclass(frozen=True)
class Content:
    """화면이 쓰는 데이터 묶음. 더미와 API 가 같은 모양을 돌려준다."""
    store: dict            # {name, branch, tables}
    categories: list       # [{id, icon, name, colors:[c1, c2]}]
    menu: list             # [{id, cat, name, desc, price, emoji, tags, soldout, weight, set_ok, ...}]
    roulette_prizes: list  # [{label, short, emoji, color, kind, percent | item_id}]
    staff_calls: list      # ["💧 물", ...]
    quiz_questions: list   # [{id, group, title, options:[{value, label, emoji}]}]
    weather: dict          # {current, types:{코드:{label, icon}}}
    rules: dict            # 조합 추천 규칙 (recommendation_data.py 참고)
    source: str            # "dummy" | "api"

    @property
    def menu_by_id(self) -> dict:
        return {m["id"]: m for m in self.menu}

    @property
    def category_by_id(self) -> dict:
        return {c["id"]: c for c in self.categories}


class DummyRepository:
    """코드 안의 더미 데이터. 주문·호출·추천 기록은 저장하지 않는다(화면 세션에만 남음)."""
    source = "dummy"

    def load_content(self) -> Content:
        import ai_quiz_data
        import menu_data
        import recommendation_data
        return Content(
            store=dict(menu_data.STORE), categories=copy.deepcopy(menu_data.CATEGORIES),
            menu=menu_data.MENU, roulette_prizes=copy.deepcopy(menu_data.ROULETTE_PRIZES),
            staff_calls=list(menu_data.STAFF_CALLS), quiz_questions=copy.deepcopy(ai_quiz_data.QUESTIONS),
            weather=copy.deepcopy(ai_quiz_data.WEATHER), rules=copy.deepcopy(recommendation_data.RULES),
            source="dummy")

    def create_order(self, table_no, lines, total, token, coupon_ids=()):
        return None

    def table_orders(self, table_no, token):
        return None

    def create_call(self, table_no, items):
        return None

    def log_recommendation(self, table_no, params, combo_ids, token):
        return None

    def generate_recommendations(self, table_no, params, lines, token):
        return None

    def db_test(self):
        return {"result": 0, "error": "더미 데이터 모드에서는 DB에 연결하지 않습니다."}


def _get_all(paths: dict) -> dict:
    """여러 GET 을 동시에 보낸다. 하나씩 보내면 (서버 왕복 시간 × 개수) 만큼 기다려야 해서 느리다."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(paths)) as pool:
        futures = {key: pool.submit(api.get, path) for key, path in paths.items()}
        return {key: f.result() for key, f in futures.items()}  # 하나라도 실패하면 그 오류가 그대로 올라간다


@st.cache_data(ttl=10, show_spinner=False)
def _fetch_live_content() -> dict:
    """관리자가 자주 바꾸는 값(메뉴·카테고리·룰렛 칸). 10초 캐시라서 바꾼 값이 곧 반영된다."""
    data = _get_all({"categories": ENDPOINTS["content"], "menus": ENDPOINTS["menus"],
                     "roulette_prizes": ENDPOINTS["roulette"]})
    return {"menus": data["menus"], "content": {"categories": data["categories"]}, "roulette_prizes": data["roulette_prizes"]}


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_static_content() -> dict:
    """거의 안 바뀌는 값(매장 정보·AI 질문·날씨·추천 규칙·직원호출 항목). 60초 캐시로 호출 횟수를 줄인다."""
    return _get_all({"store": ENDPOINTS["store"], "questions": ENDPOINTS["questions"], "weather": ENDPOINTS["weather"],
                     "rules": ENDPOINTS["rules"], "staff_call_items": ENDPOINTS["staff_call_items"]})


def _fetch_content() -> dict:
    """서버에서 화면 콘텐츠를 가져온다. 바뀌는 값은 10초, 거의 안 바뀌는 값은 60초 캐시."""
    data = {**_fetch_static_content(), **_fetch_live_content()}
    missing = [k for k in CONTENT_KEYS if k not in data["content"]]
    if missing:
        raise api.ApiError(502, f"서버 응답에 {missing} 가 없습니다.")
    return data


class ApiRepository:
    """서버(API)에서 가져온다. 응답 모양은 더미와 같으므로 변환 없이 쓴다."""
    source = "api"

    def load_content(self) -> Content:
        try:
            data = _fetch_content()
        except api.ApiUnavailable as e:
            server.mark_offline()
            raise ContentUnavailable("서버에 연결할 수 없습니다.") from e
        except api.ApiError as e:
            raise ContentUnavailable(f"서버 응답을 읽지 못했습니다. ({e.detail})") from e
        menu = data["menus"]
        for m in menu:
            m.setdefault("options", [])  # 옵션 기능은 아직 서버에 없다
        c = data["content"]
        return Content(store=data["store"], categories=c["categories"], menu=menu,
                       roulette_prizes=data["roulette_prizes"], staff_calls=data["staff_call_items"],
                       quiz_questions=data["questions"], weather=data["weather"], rules=data["rules"], source="api")

    def create_order(self, table_no, lines, total, token, coupon_ids=()):
        r = server.safe_call(api.post, ENDPOINTS["orders"], token,
                             json={"table_no": table_no, "lines": lines, "total": total, "coupon_ids": list(coupon_ids)})
        return r["no"] if r else None

    def table_orders(self, table_no, token):
        return server.table_orders(token, table_no)

    def create_call(self, table_no, items):
        r = server.safe_call(api.post, ENDPOINTS["calls"], None, json={"table_no": table_no, "items": items})
        return r["id"] if r else None

    def log_recommendation(self, table_no, params, combo_ids, token):
        r = server.safe_call(api.post, ENDPOINTS["recommendations"], token,
                             json={"table_no": table_no, "params": params, "combo_ids": combo_ids})
        return r["id"] if r else None

    def generate_recommendations(self, table_no, params, lines, token):
        """DB와 제미나이를 사용하는 서버 추천을 요청한다. 실패하면 화면이 규칙 추천으로 대체한다."""
        return server.safe_call(api.post, ENDPOINTS["recommendation_generate"], token,
                                json={"table_no": table_no, "params": params, "lines": lines})

    def db_test(self):
        """개발 전용 API를 호출한다. 오류는 화면에서 이유를 표시할 수 있도록 그대로 전달한다."""
        return api.post("/api/dev/db-test")


class AutoRepository:
    """서버가 닿으면 API, 아니면 더미. 쓰기는 서버가 안 닿으면 조용히 건너뛴다."""

    def __init__(self):
        self._api, self._dummy = ApiRepository(), DummyRepository()
        self.source = "dummy"

    def load_content(self) -> Content:
        if server.is_online():
            try:
                content = self._api.load_content()
                self.source = "api"
                return content
            except ContentUnavailable:
                pass
        self.source = "dummy"
        return self._dummy.load_content()

    def create_order(self, *a, **kw):
        return self._api.create_order(*a, **kw) if self.source == "api" else None

    def table_orders(self, *a, **kw):
        return self._api.table_orders(*a, **kw) if self.source == "api" else None

    def create_call(self, *a, **kw):
        return self._api.create_call(*a, **kw) if self.source == "api" else None

    def log_recommendation(self, *a, **kw):
        return self._api.log_recommendation(*a, **kw) if self.source == "api" else None

    def generate_recommendations(self, *a, **kw):
        return self._api.generate_recommendations(*a, **kw) if self.source == "api" else None

    def db_test(self):
        # 콘텐츠가 더미로 전환됐더라도 이 버튼은 실제 서버·DB 연결을 직접 확인해야 한다.
        return self._api.db_test()


def data_source_mode() -> str:
    mode = os.getenv("DATA_SOURCE", "auto").strip().lower()
    return mode if mode in MODES else "auto"


def get_repository():
    """DATA_SOURCE 에 맞는 저장소. 화면은 이 함수만 부른다."""
    mode = data_source_mode()
    return DummyRepository() if mode == "dummy" else ApiRepository() if mode == "api" else AutoRepository()


def load_content():
    """(저장소, 콘텐츠). api 모드에서 서버가 안 닿으면 ContentUnavailable."""
    repo = get_repository()
    return repo, repo.load_content()
