"""user 페이지의 서버 연동 계층 (QR 로그인·회원 정보). 서버가 없으면 None 을 돌려주고 해당 기능만 꺼진다."""
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import httpx
import streamlit as st
from urllib.parse import urlparse

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


def tablet_logins(token: str, table_no: int):
    """이 태블릿에서 로그인한 회원 기록 [{id, nickname, at(UTC ISO), eligible, prize}] 또는 None."""
    return safe_call(api.get, f"/api/tables/{table_no}/logins", token)


def save_prize(token: str, table_no: int, member_id: int, prize: dict):
    """룰렛 결과를 서버에 남겨 새로고침 뒤에도 '이미 돌렸다'가 유지되게 하고, 쿠폰함에 쿠폰으로 넣는다.
    prize 는 콘텐츠의 룰렛 칸({short, emoji, kind, percent | item_id}). 발급된 쿠폰 dict 를 돌려주고, 서버가 안 닿으면 None."""
    body = {"member_id": member_id, "prize": prize["short"], "kind": prize["kind"], "emoji": prize.get("emoji", "🎁"),
            "percent": prize.get("percent"), "item_id": prize.get("item_id")}
    r = safe_call(api.put, f"/api/tables/{table_no}/logins/prize", token, json=body)
    return r["coupon"] if r else None


def table_coupons(token: str, table_no: int):
    """이 태블릿에 로그인한 회원들의 쿠폰 [{id, member_id, nickname, kind, label, emoji, percent, item_id, used_at}] 또는 None."""
    return safe_call(api.get, f"/api/tables/{table_no}/coupons", token)


DEV_NICKNAME = "개발테스트"  # APP_ENV=dev 자동 로그인에 쓰는 모의 카카오 회원 닉네임


def dev_login(table_no: int):
    """(개발 전용) 휴대폰 없이 모의 카카오 로그인을 서버에 직접 거쳐 {event:'logged_in', member, access_token} 을 얻는다.

    실제 QR 로그인과 같은 서버 API 를 그대로 쓰므로 회원·로그인 기록이 정상적으로 만들어진다.
    서버가 꺼져 있거나 모의 로그인이 아닌 서버(카카오 키 설정됨)면 None 이고, 그때는 평소처럼 QR 로그인을 쓴다.
    """
    qr = create_qr(table_no)
    if not qr:
        return None
    url = urlparse(qr["qr_url"])
    token = url.query.removeprefix("token=")
    try:
        http = api._http()
        http.get(f"{url.path}?{url.query}")  # QR 을 스캔한 것으로 처리
        http.get("/api/auth/kakao/continue", params={"token": token})  # 광고 문자 수신 동의는 하지 않음
        http.get("/api/auth/kakao/callback", params={"state": token, "code": f"mock-{DEV_NICKNAME}"})
    except httpx.HTTPError:
        mark_offline()
        return None
    event = poll_login(qr["secret"])
    return event if event and event.get("event") == "logged_in" else None
