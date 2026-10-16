"""QR 로그인 상태 (발급·확인·완료 처리).
"""

import time
from datetime import datetime

import streamlit as st

import server
from shared import api
from user.state.coupons import load_coupons
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
    mine = next((r for r in server.tablet_logins(ss.access_token, ss.table) or [] if r["id"] == m["id"]), None)
    if mine and not mine["eligible"]:  # 오늘 다른 테이블에서 이미 룰렛을 돌린 회원은 기회가 없다
        first = False
        ss.granted_ids.append(m["id"])
    if first:
        ss.granted_ids.append(m["id"])
    ss.members.append({"id": m["id"], "nickname": m["nickname"], "at": datetime.now(KST).strftime("%H:%M"),
                       "eligible": first, "prize": None})
    load_coupons()  # 이전에 받아 둔 안 쓴 쿠폰이 있으면 쿠폰함에 보인다


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
        _restore_members(token, m)


def dev_auto_login():
    """APP_ENV=dev 일 때만, 로그인 안 된 손님 앱을 모의 회원으로 자동 로그인시킨다 (개발 중 매번 QR 로그인을 거치지 않으려는 용도).

    APP_ENV 가 dev 가 아니면(운영·미설정) 아무것도 하지 않는다. 세션당 한 번만 시도한다.
    """
    ss = st.session_state
    if not api.is_dev() or ss.member or ss.get("_dev_login_tried"):
        return
    ss._dev_login_tried = True
    event = server.dev_login(ss.table)
    if event:
        finish_login(event)  # 서버가 회원·로그인 기록을 DB 에 INSERT 하고 토큰을 준 경우
        return
    # 서버가 꺼져 있거나 DB INSERT 가 안 되는 경우에도 개발 화면은 로그인된 것처럼 보이게 임시 회원을 둔다.
    # 토큰이 없어 서버 기능(쿠폰 저장 등)은 못 쓰지만 화면 흐름은 확인할 수 있다.
    ss.member = {"id": 0, "nickname": server.DEV_NICKNAME}
    ss.members = [{"id": 0, "nickname": server.DEV_NICKNAME, "at": datetime.now(KST).strftime("%H:%M"),
                   "eligible": False, "prize": None}]
    ss.granted_ids = [0]


def _restore_members(token, m):
    """서버에 남은 '이 태블릿 로그인 기록'(룰렛 사용 여부 포함)을 되살린다. 못 받으면 현재 회원만 기록한다."""
    ss = st.session_state
    rows = server.tablet_logins(token, ss.table)
    if not rows:  # 서버가 기록을 못 줘도 현재 회원은 룰렛을 이미 쓴 것으로 보고 중복 로그인을 막는다
        rows = [{"id": m["id"], "nickname": m["nickname"], "at": None, "eligible": False, "prize": None}]
    ss.members = [{"id": r["id"], "nickname": r["nickname"], "at": _hhmm(r["at"]),
                   "eligible": r["eligible"], "prize": r["prize"]} for r in rows]
    ss.granted_ids = [r["id"] for r in rows]
    load_coupons()


def _hhmm(iso):
    return datetime.fromisoformat(iso).astimezone(KST).strftime("%H:%M") if iso else ""


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
