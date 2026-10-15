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
    qr = server.create_qr(st.session_state.table, prev["secret"] if prev else None)
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
    ss.member, ss.access_token, ss.login = m, event["access_token"], None
    first = m["id"] not in ss.granted_ids
    if first:
        ss.granted_ids.append(m["id"])
    ss.members.append({"id": m["id"], "nickname": m["nickname"], "at": datetime.now(KST).strftime("%H:%M"),
                       "eligible": first, "prize": None})
    ss.profile_saved = False


def poll_login_once():
    """진행 중인 QR 로그인이 있으면 서버에 한 번 물어보고, 완료됐으면 반영한다."""
    ss = st.session_state
    if not ss.login:
        return None
    event = server.poll_login(ss.login["secret"])
    if event and event.get("event") == "logged_in":
        finish_login(event)
    return event
