"""여러 화면이 같이 쓰는 UI 조각 (금액 표기·상단 버튼·썸네일).
"""

import streamlit as st

from ai_quiz_data import KST  # noqa: F401  (다른 화면이 여기서 가져간다)
from menu_images import menu_image_html
from user.state import context as ctx
from user.state.session import go, toggle_theme


def won(n):
    return f"{n:,}원"


def mini_buttons(prefix, home=True):
    """우측 상단의 작은 '처음으로'·다크/라이트 전환 버튼. 전환 버튼은 눌러야 할 다음 모드를 아이콘으로 보여 준다."""
    light = st.session_state.theme == "light"
    with st.container(horizontal=True, key=f"{prefix}_mini"):
        if home:
            st.button("🏠", key=f"{prefix}_home", help="처음으로", on_click=go, args=("splash",))
        st.button("🌙" if light else "☀️", key=f"{prefix}_theme", help="다크 모드" if light else "라이트 모드",
                  on_click=toggle_theme)


def scroll_to_top_on_view_change():
    """화면(페이지·카테고리·AI 질문 단계)이 바뀌면 모든 스크롤 영역을 맨 위로 올린다."""
    ss = st.session_state
    view = (ss.page, ss.cat if ss.page == "menu" else None, ss.quiz["step"] if ss.page == "ai_quiz" else None)
    if ss.get("_view") == view:
        return
    first = "_view" not in ss
    ss._view = view
    if first:
        return
    ss._scroll_n = ss.get("_scroll_n", 0) + 1
    st.html(f"""<script>/* {ss._scroll_n} */
const up = () => {{
  window.scrollTo(0, 0);
  document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"], .stApp, [class*="st-key-quiz_page"], [data-testid="stColumn"]')
    .forEach(e => {{ e.scrollTop = 0; }});
}};
up(); setTimeout(up, 60); setTimeout(up, 250);
</script>""", unsafe_allow_javascript=True)


def spicy_level(item):
    """매운 정도(고추 개수). 매운맛 태그가 없으면 0."""
    if "매운맛" not in item["tags"]:
        return 0
    name = item["name"]
    if "아주 매운맛" in name:
        return 3
    if "보통맛" in name or "얼큰" in item["desc"]:
        return 2
    return 1


def thumb_html(item, qty_in_cart=0, big=False):
    c1, c2 = ctx.CATEGORY_BY_ID[item["cat"]]["colors"]
    size = " big" if big else ""
    badges = ""
    for t in item["tags"]:
        badges += (f'<span class="badge spicy">{"🌶" * spicy_level(item)} 매운맛</span>'
                   if t == "매운맛" else f'<span class="badge {t}">{t}</span>')
    extra = f'<div class="incart">{qty_in_cart}개 담김</div>' if qty_in_cart else ""
    sold = '<div class="soldout">품절</div>' if item["soldout"] else ""
    return (f'<div class="thumb{size}" style="background:linear-gradient(135deg,{c1},{c2})">'
            f'{menu_image_html(item)}<div class="badges">{badges}</div>{extra}{sold}</div>')
