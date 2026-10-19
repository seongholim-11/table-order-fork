"""관리자 로그인 화면.
"""

import json

import streamlit as st

import admin_repository as repo_mod

ss = st.session_state

COOKIE = "owner_token"  # 사장님 로그인 토큰을 보관하는 브라우저 쿠키 이름 (새로고침해도 로그인을 유지하려고 쓴다)
COOKIE_SECONDS = 3600  # Supabase 토큰 기본 유효기간(1시간)에 맞춘다. 토큰이 만료되면 복원에 실패하고 로그인 화면으로 돌아간다


def _set_cookie(value: str, max_age: int) -> None:
    """브라우저에 쿠키를 쓴다. Streamlit 은 서버에서 쿠키를 쓸 수 없어서 짧은 JavaScript 를 실행한다."""
    st.html(f"<script>document.cookie = {json.dumps(COOKIE)} + '=' + {json.dumps(value)} + "
            f"'; path=/; max-age={max_age}; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');</script>",
            unsafe_allow_javascript=True)


def remember_token(token: str) -> None:
    _set_cookie(token, COOKIE_SECONDS)


def forget_token() -> None:
    _set_cookie("", 0)  # max-age=0 이면 브라우저가 쿠키를 지운다


def saved_token() -> str:
    """새로고침 전에 저장해 둔 사장님 토큰. 없거나 읽을 수 없으면 빈 문자열."""
    try:
        return st.context.cookies.get(COOKIE, "") or ""
    except Exception:  # 쿠키를 읽을 수 없는 환경(테스트 등)에서는 저장된 토큰이 없는 것으로 본다
        return ""


def login():
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.html('<div style="height:8vh"></div><div style="text-align:center;margin-bottom:22px">'
                '<div class="sb-logo" style="width:56px;height:56px;border-radius:16px;font-size:30px;margin:0 auto 14px">🍺</div>'
                '<div style="font-size:26px;font-weight:800;letter-spacing:-.02em">F&B Growth 관리자</div>'
                '<div style="color:#8a857e;font-size:14px;margin-top:6px">사장님 전용 관리 화면이에요</div></div>')
        if repo_mod.owner_login_enabled():
            # 사장님 계정(Supabase)으로 로그인. 개발용 토큰 입력은 아래 접이식에 둔다.
            with st.container(border=True):
                email = st.text_input("이메일", placeholder="owner@example.com")
                password = st.text_input("비밀번호", type="password")
                if st.button("사장님 로그인", type="primary", width="stretch"):
                    result = repo_mod.connect_owner(email, password)
                    if result.error:
                        st.error(result.error)
                    else:
                        ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, result.repo, result.token, result.notice
                        ss["remember_token"] = True  # 다음 화면에서 쿠키에 저장한다(지금 바로 rerun 하면 스크립트가 실행되지 않는다)
                        st.rerun()
            st.caption("사장님으로 등록된 계정만 들어올 수 있어요.")
            return
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
