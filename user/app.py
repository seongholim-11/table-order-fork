"""티오더 스타일 테이블 오더 - 역전할머니맥주 (Streamlit 데모)

실행: streamlit run app.py

진입점: 데이터 로드 → 세션 초기화 → 현재 page 에 맞는 화면 선택만 한다.
  state/  세션 상태와 계산 (장바구니·로그인·룰렛·AI 질문)
  ui/     재사용 UI 조각과 다이얼로그
  views/  화면 (스플래시·주문·AI 추천/질문)
(폴더 이름이 pages 가 아니라 views 인 이유: Streamlit 은 pages/ 폴더를 자동 멀티페이지로 인식한다.)
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))  # 저장소 루트: user.*, shared.* 를 import 하기 위해

import user_repository as repository  # noqa: E402
from user.state import context as ctx  # noqa: E402
from user.state.login import dev_auto_login, restore_login, sync_login_url  # noqa: E402
from user.state.session import init_state, sync_url  # noqa: E402
from user.ui.cart import render_cart  # noqa: E402
from user.ui.common import scroll_to_top_on_view_change  # noqa: E402
from user.ui.dialogs import confirm_dialog  # noqa: E402
from user.views.ai import quiz_at_result, render_ai_quiz  # noqa: E402
from user.views.order import render_categories, render_header, render_menu  # noqa: E402
from user.views.splash import render_splash  # noqa: E402

# 화면에 쓰는 모든 데이터는 repository 를 거친다 (DATA_SOURCE=dummy|api|auto, user_repository.py 참고).
try:
    ctx.load()
except repository.ContentUnavailable as e:
    st.set_page_config(page_title="테이블오더", page_icon="🍺")
    st.error(f"{e} 직원에게 문의해 주세요.")
    st.stop()

st.set_page_config(page_title=f"{ctx.STORE['name']} 테이블오더", page_icon="🍺",
                   layout="wide", initial_sidebar_state="collapsed")


def main():
    init_state()
    restore_login()
    dev_auto_login()  # APP_ENV=dev 일 때만 모의 회원으로 자동 로그인
    sync_url()
    st.html(Path(__file__).with_name("app.css"))
    if st.session_state.theme == "light":
        st.html(Path(__file__).with_name("app_light.css"))
    scroll_to_top_on_view_change()
    sync_login_url()
    if st.session_state.page == "splash":
        render_splash()
        return
    render_header()
    if st.session_state.page == "ai_quiz":
        if quiz_at_result():  # 결과 화면에는 주문 화면처럼 오른쪽에 장바구니를 함께 보여 준다
            with st.container(key="quiz_result_layout"):
                c_quiz, c_cart = st.columns([5.2, 2.5], gap="medium")
            with c_quiz:
                render_ai_quiz()
            with c_cart:
                render_cart()
        else:
            render_ai_quiz()
        if st.session_state.pop("confirm_order", False):
            confirm_dialog()
        return
    with st.container(key="order_layout"):
        c_cat, c_menu, c_cart = st.columns([1.15, 5.2, 2.5], gap="medium")
    with c_cat:
        with st.container(key="categories"):
            render_categories()
    with c_menu:
        render_menu()
    with c_cart:
        render_cart()
    if st.session_state.pop("confirm_order", False):
        confirm_dialog()


main()
