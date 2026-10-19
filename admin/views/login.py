"""관리자 로그인 화면.
"""

import streamlit as st

import admin_repository as repo_mod

ss = st.session_state


def login():
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.html('<div style="height:8vh"></div><div style="text-align:center;margin-bottom:22px">'
                '<div class="sb-logo" style="width:56px;height:56px;border-radius:16px;font-size:30px;margin:0 auto 14px">🍺</div>'
                '<div style="font-size:26px;font-weight:800;letter-spacing:-.02em">F&B Growth 관리자</div>'
                '<div style="color:#8a857e;font-size:14px;margin-top:6px">사장님 전용 관리 화면이에요</div></div>')
        with st.container(border=True):
            token = st.text_input("관리자 토큰", type="password", placeholder="토큰을 입력하세요")
            if st.button("로그인", type="primary", width="stretch"):
                result = repo_mod.connect(token)
                if result.error:
                    st.error(result.error)
                else:
                    ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, result.repo, token, result.notice
                    st.rerun()
        st.caption("백엔드 `.env`의 `ADMIN_TOKEN` 값을 입력하세요. (기본값 `change-me`) "
                   "OWNER(사장님)만 접근할 수 있고, MANAGER·STAFF 권한은 1차 Prototype에서 사용하지 않습니다.")
