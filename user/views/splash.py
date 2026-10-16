"""시작(스플래시) 화면: 룰렛 + 로그인 + 주문 시작.
"""

import os
from html import escape

import streamlit as st

from shared import api
from user.state import context as ctx
from user.state.login import poll_login_once
from user.state.roulette import spins_left
from user.state.session import go
from user.ui.common import mini_buttons
from user.ui.login import login_dialog, render_members_log
from user.ui.roulette import render_roulette


def render_splash():
    ss = st.session_state
    poll_login_once()  # 팝업을 닫았거나 다시 그려진 뒤에도 완료된 로그인은 반영
    mini_buttons("splash", home=False)
    store = ctx.STORE  # 매장 정보(이름·지점)는 서버가 Supabase store_info 테이블에서 읽어 준다
    st.html(f'<div class="brand splash-brand"><div class="logo">🍺</div><div><div class="name">{escape(store["name"])}</div>'
            f'<div class="sub">{escape(store["branch"])}</div></div></div>')
    render_roulette()
    member = ss.member
    with st.container(horizontal=True, key="splash_bottom"):
        with st.container(horizontal=True, key="qr_card"):
            if member:
                st.html(f'<div class="qr-text"><div class="a">{escape(member["nickname"])}님</div>'
                        '<div class="b">회원 로그인 완료!</div>'
                        f'<div class="c">남은 룰렛 기회 {spins_left()}회</div></div>')
            else:
                st.html('<div class="qr-text"><div class="a">회원이신가요?</div><div class="b">로그인하고 룰렛 돌리기</div>'
                        '<div class="c">로그인하지 않아도<br>주문은 할 수 있어요.</div></div>')
            if st.button("➕ 다른 회원 로그인" if member else "📱 로그인", key="login_open"):
                login_dialog("more")
            if os.getenv("DEV_TEST_BUTTON", "").strip().lower() in ("1", "true"):
                if st.button("🧪 DB 테스트", key="dev_db_test"):
                    try:
                        result = ctx.REPO.db_test()
                        st.success(str(result["result"]))
                    except (api.ApiError, api.ApiUnavailable) as e:
                        # 개발자가 연결·설정 문제를 바로 찾을 수 있도록 실패 이유를 버튼 옆에 표시한다.
                        st.error(f"DB 테스트 실패: {e}")
        with st.container(key="start_cta"):
            st.button("🍴 회원 주문  ›" if member else "🍴 비회원 주문  ›", type="primary", width="stretch",
                      key="start_btn", on_click=go, args=("menu",))
    render_members_log()
