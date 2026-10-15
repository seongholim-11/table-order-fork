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


def create_qr(table_no: int, previous_secret: str | None = None):
    """{token, secret, qr_url, expires_in} 또는 None. previous_secret 을 주면 이전 QR 세션을 정리하고 새로 발급한다."""
    body = {"table_no": table_no, **({"previous_secret": previous_secret} if previous_secret else {})}
    return safe_call(api.post, "/api/auth/qr", None, json=body)


def poll_login(secret: str):
    """{event:'status', status, remaining} / {event:'logged_in', member, access_token} 또는 None."""
    return safe_call(api.get, f"/api/auth/qr/{secret}")
