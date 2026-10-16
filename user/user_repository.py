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
    "content": "/api/content",                # {categories, staff_calls, quiz_questions, weather, rules}
    "roulette": "/api/v1/roulette/prizes",    # 관리자 설정과 같은 DB의 룰렛 칸
    "orders": "/api/orders",                  # POST
    "calls": "/api/calls",                    # POST
    "recommendations": "/api/recommendations",  # POST (추천 노출 기록)
}
CONTENT_KEYS = ("categories", "staff_calls", "quiz_questions", "weather", "rules")
MODES = ("dummy", "api", "auto")


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

    def create_call(self, table_no, items):
        return None

    def log_recommendation(self, table_no, params, combo_ids, token):
        return None

    def db_test(self):
        return {"result": 0, "error": "더미 데이터 모드에서는 DB에 연결하지 않습니다."}


@st.cache_data(ttl=10, show_spinner=False)
def _fetch_content() -> dict:
    """서버에서 한 번에 가져온다 (10초 캐시: 관리자가 바꾼 가격·품절이 곧 반영된다)."""
    data = {"store": api.get(ENDPOINTS["store"]), "menus": api.get(ENDPOINTS["menus"]),
            "content": api.get(ENDPOINTS["content"]), "roulette_prizes": api.get(ENDPOINTS["roulette"])}
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
                       roulette_prizes=data["roulette_prizes"], staff_calls=c["staff_calls"],
                       quiz_questions=c["quiz_questions"], weather=c["weather"], rules=c["rules"], source="api")

    def create_order(self, table_no, lines, total, token, coupon_ids=()):
        r = server.safe_call(api.post, ENDPOINTS["orders"], token,
                             json={"table_no": table_no, "lines": lines, "total": total, "coupon_ids": list(coupon_ids)})
        return r["no"] if r else None

    def create_call(self, table_no, items):
        r = server.safe_call(api.post, ENDPOINTS["calls"], None, json={"table_no": table_no, "items": items})
        return r["id"] if r else None

    def log_recommendation(self, table_no, params, combo_ids, token):
        r = server.safe_call(api.post, ENDPOINTS["recommendations"], token,
                             json={"table_no": table_no, "params": params, "combo_ids": combo_ids})
        return r["id"] if r else None

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

    def create_call(self, *a, **kw):
        return self._api.create_call(*a, **kw) if self.source == "api" else None

    def log_recommendation(self, *a, **kw):
        return self._api.log_recommendation(*a, **kw) if self.source == "api" else None

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
