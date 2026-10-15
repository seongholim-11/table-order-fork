"""user 페이지의 서버 연동 계층 (QR 로그인·회원 정보). 서버가 없으면 None 을 돌려주고 해당 기능만 꺼진다."""
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from shared import api

RETRY_AFTER = 15  # 서버가 안 닿으면 이 시간(초) 동안은 다시 시도하지 않는다 (화면이 매번 멈추지 않게)


def is_online() -> bool:
    return st.session_state.get("offline_until", 0) <= time.time()


def mark_offline() -> None:
    st.session_state["offline_until"] = time.time() + RETRY_AFTER


def safe_call(fn, *args, **kw):
    """서버 호출. 실패하면 None 을 돌려주고 한동안 오프라인으로 본다."""
    if not is_online():
        return None
    try:
        return fn(*args, **kw)
    except api.ApiUnavailable:
        mark_offline()
    except api.ApiError:
        pass
    return None


def create_qr(table_no: int, previous_secret: str | None = None, logged_in_member_ids: list | None = None):
    """{token, secret, qr_url, expires_in} 또는 None. previous_secret 을 주면 이전 QR 세션을 정리하고 새로 발급한다. logged_in_member_ids 의 회원은 이 QR로 다시 로그인할 수 없다."""
    body = {"table_no": table_no, "logged_in_member_ids": logged_in_member_ids or [],
            **({"previous_secret": previous_secret} if previous_secret else {})}
    return safe_call(api.post, "/api/auth/qr", None, json=body)


def poll_login(secret: str):
    """{event:'status', status, remaining} / {event:'logged_in', member, access_token} 또는 None."""
    return safe_call(api.get, f"/api/auth/qr/{secret}")


def restore_member(token: str):
    """저장해 둔 토큰으로 회원을 다시 확인한다. 'invalid'(만료·위조), None(서버 연결 불가), 회원 dict 중 하나."""
    if not is_online():
        return None
    try:
        return api.get("/api/members/me", token)
    except api.ApiError as e:
        return "invalid" if e.status in (401, 403, 404) else None
    except api.ApiUnavailable:
        mark_offline()
        return None
