"""화면이 읽는 매장 데이터 (메뉴·카테고리·룰렛 상품·규칙 등).

app.py 가 매 실행 처음에 load() 로 저장소에서 읽어 세션에 보관하고, 다른 모듈은 `ctx.MENU` 처럼 쓴다.
(모듈 import 시점에 읽지 않는 이유: 데이터가 10초마다 갱신되고, 세션마다 따로 보관해야 하기 때문)
"""

import streamlit as st

import user_repository as repository


def load() -> None:
    """저장소에서 데이터를 읽는다. 읽지 못하면 repository.ContentUnavailable 이 난다."""
    repo, content = repository.load_content()
    st.session_state["_ctx"] = (repo, content)
    st.session_state.data_source = content.source  # "dummy" | "api" (점검·테스트용 표시)


def __getattr__(name: str):
    # Streamlit 파일 감시기가 세션 밖에서 hasattr(module, "__path__") 를 부르면 KeyError 대신 AttributeError 여야 한다.
    if name.startswith("__") or "_ctx" not in st.session_state:
        raise AttributeError(name)
    repo, c = st.session_state["_ctx"]
    values = {
        "REPO": repo, "CONTENT": c, "STORE": c.store, "CATEGORIES": c.categories, "CATEGORY_BY_ID": c.category_by_id,
        "MENU": c.menu, "MENU_BY_ID": c.menu_by_id, "ROULETTE_PRIZES": c.roulette_prizes, "STAFF_CALLS": c.staff_calls,
        "QUESTIONS": c.quiz_questions, "WEATHER": c.weather, "RULES": c.rules,
        "DISCOUNT_PERCENT": c.rules["discount_percent"],
    }
    if name in values:
        return values[name]
    raise AttributeError(name)
