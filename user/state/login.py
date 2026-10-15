"""QR 로그인 상태 (발급·확인·완료 처리).
"""

import time
from datetime import datetime

import streamlit as st

import server
from user.ui.common import KST


def new_login():
    """서버에서 일회용 QR 로그인 세션을 발급받는다. 서버가 없으면 None. 이전 QR 세션은 서버에서 정리한다."""
    prev = st.session_state.login
    qr = server.create_qr(st.session_state.table, prev["secret"] if prev else None,
                         [m["id"] for m in st.session_state.members])
    if qr or not prev:
        st.session_state.login = {**qr, "created": time.time()} if qr else None


def ensure_login():
    login = st.session_state.login
    if not login or time.time() - login["created"] > login["expires_in"]:
        new_login()


def finish_login(event):
    """로그인 완료: 이 태블릿의 회원 기록에 누적하고, 처음 로그인한 회원에게만 룰렛 기회를 준다."""
    ss = st.session_state
    m = event["member"]
    if any(r["id"] == m["id"] for r in ss.members):  # 서버가 막지만, 못 막은 경우에도 중복 기록은 만들지 않는다
        ss.login = None
        return
    ss.member, ss.access_token, ss.login = m, event["access_token"], None
    ss._cookie_cmd = event["access_token"]
    first = m["id"] not in ss.granted_ids
    if first:
        ss.granted_ids.append(m["id"])
    ss.members.append({"id": m["id"], "nickname": m["nickname"], "at": datetime.now(KST).strftime("%H:%M"),
                       "eligible": first, "prize": None})


COOKIE = "to_token"
COOKIE_MAX_AGE = 12 * 3600  # 서버 JWT 기본 유효 시간(JWT_EXPIRE_MINUTES=720)과 맞춘다


def restore_login():
    """새로고침으로 세션이 비었을 때, 브라우저 쿠키에 저장된 토큰으로 로그인 상태를 되살린다."""
    ss = st.session_state
    if ss.member or ss.get("_login_restored"):
        return
    ss._login_restored = True
    token = st.context.cookies.get(COOKIE)
    if not token:
        return
    me = server.restore_member(token)
    if me == "invalid":
        ss._cookie_cmd = ""  # 만료된 토큰은 쿠키에서 지운다
    elif me:
        ss.member, ss.access_token = {"id": me["id"], "nickname": me["nickname"]}, token
        if me["id"] not in ss.granted_ids:  # 룰렛 기회는 로그인 때 이미 한 번 받은 것으로 본다
            ss.granted_ids.append(me["id"])


def sync_login_cookie():
    """로그인 직후엔 토큰을 브라우저 쿠키에 저장한다 (쿠키는 이 브라우저에서만 쓰이며 12시간 뒤 사라진다)."""
    ss = st.session_state
    cmd = ss.pop("_cookie_cmd", None)
    if cmd is None:
        return
    age = COOKIE_MAX_AGE if cmd else 0
    st.html(f"""<script>
document.cookie = {COOKIE!r} + "=" + {cmd!r} + "; path=/; max-age={age}; SameSite=Lax";
</script>""", unsafe_allow_javascript=True)


def poll_login_once():
    """진행 중인 QR 로그인이 있으면 서버에 한 번 물어보고, 완료됐으면 반영한다."""
    ss = st.session_state
    if not ss.login:
        return None
    event = server.poll_login(ss.login["secret"])
    if event and event.get("event") == "logged_in":
        finish_login(event)
    return event
