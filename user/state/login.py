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
    st.query_params[TOKEN_PARAM] = ss.access_token
    first = m["id"] not in ss.granted_ids
    if first:
        ss.granted_ids.append(m["id"])
    ss.members.append({"id": m["id"], "nickname": m["nickname"], "at": datetime.now(KST).strftime("%H:%M"),
                       "eligible": first, "prize": None})


TOKEN_PARAM = "t"  # 로그인 토큰을 담는 URL 쿼리. 쿠키는 Streamlit Cloud 의 iframe 안에서 막혀 URL 로 유지한다.


def restore_login():
    """새로고침으로 세션이 비었을 때, URL(?t=토큰)에 담긴 토큰으로 로그인 상태를 되살린다."""
    ss = st.session_state
    if ss.member or ss.get("_login_restored"):
        return
    ss._login_restored = True
    token = st.query_params.get(TOKEN_PARAM)
    if not token:
        return
    me = server.restore_member(token)
    if me == "invalid":
        st.query_params.pop(TOKEN_PARAM, None)  # 만료·위조된 토큰은 지운다
    elif me:
        m = {"id": me["id"], "nickname": me["nickname"]}
        ss.member, ss.access_token = m, token
        if m["id"] not in ss.granted_ids:  # 룰렛 기회는 로그인 때 이미 한 번 받은 것으로 본다
            ss.granted_ids.append(m["id"])
        if all(r["id"] != m["id"] for r in ss.members):  # 이 태블릿 로그인 기록에도 남겨 중복 로그인을 막는다
            ss.members.append({"id": m["id"], "nickname": m["nickname"], "at": datetime.now(KST).strftime("%H:%M"),
                               "eligible": False, "prize": None})


def sync_login_url():
    """로그인한 회원의 토큰을 URL 에 반영한다 (새로고침해도 유지, 서버 JWT 만료 시 자동으로 무효)."""
    token = st.session_state.access_token
    if st.session_state.member and token and st.query_params.get(TOKEN_PARAM) != token:
        st.query_params[TOKEN_PARAM] = token


def poll_login_once():
    """진행 중인 QR 로그인이 있으면 서버에 한 번 물어보고, 완료됐으면 반영한다."""
    ss = st.session_state
    if not ss.login:
        return None
    event = server.poll_login(ss.login["secret"])
    if event and event.get("event") == "logged_in":
        finish_login(event)
    return event
