"""QR 로그인 API. 흐름은 docs/PRODUCTION_PLAN.md 1장 참고.

태블릿: POST /qr → 화면에 QR 표시 → WS /ws/{secret} 로 대기
휴대폰: QR(= /kakao/start) → 광고성 문자 수신 동의(선택) → 카카오 로그인 → /kakao/callback
"""

import asyncio
import html

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings
from app.services import tokens
from app.services.kakao import KakaoError
from app.services.supabase_auth import SupabaseAuthError, new_pkce_pair

router = APIRouter(prefix="/api/auth", tags=["QR 로그인"])


class QrRequest(BaseModel):
    table_no: int = Field(ge=1)
    previous_secret: str | None = None  # QR 재생성: 이전 세션을 먼저 정리한다


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<body style="font-family:sans-serif;text-align:center;padding:48px 20px">'
        f"<h2>{html.escape(title)}</h2><p>{body}</p></body>", status_code=status)


def _public_member(m: dict) -> dict:
    return {"id": m["id"], "nickname": m["nickname"]}


@router.post("/qr")
async def create_qr(body: QrRequest, request: Request, settings: Settings = Depends(get_settings)):
    store = request.app.state.login_store
    if body.previous_secret:
        store.discard(body.previous_secret)
    s = store.create(body.table_no)
    return {"token": s.token, "secret": s.secret, "expires_in": int(store.ttl),
            "qr_url": f"{settings.public_base_url}/api/auth/kakao/start?token={s.token}"}


@router.get("/qr/{secret}")
async def poll_status(secret: str, request: Request):
    """WebSocket을 쓸 수 없을 때의 폴링. 로그인 결과(JWT)는 한 번만 내려간다."""
    store = request.app.state.login_store
    s = store.by_secret(secret)
    if not s:
        raise HTTPException(404, "없는 로그인 세션입니다.")
    status = store.status(s)
    if status == "logged_in":
        return store.claim(s) or {"event": "status", "status": "claimed"}
    return {"event": "status", "status": status, "remaining": int(store.remaining(s))}


@router.get("/kakao/start")
async def kakao_start(token: str, request: Request, settings: Settings = Depends(get_settings)):
    """QR을 스캔한 휴대폰이 여는 주소. 스캔 상태로 바꾸고 카카오 로그인으로 보낸다."""
    store = request.app.state.login_store
    s = store.by_token(token)
    if not s:
        return _page("유효하지 않은 QR입니다", "태블릿에서 QR을 새로 받아 주세요.", 404)
    if not store.mark_scanned(s):
        msg = "이미 사용된 QR입니다." if store.status(s) == "logged_in" else "QR이 만료되었습니다."
        return _page("로그인할 수 없어요", msg + " 태블릿에서 새 QR을 받아 주세요.", 410)
    return _consent_page(token)


def _consent_page(token: str) -> HTMLResponse:
    """카카오 로그인 전에 광고성 문자 수신 동의(선택)를 받는 화면."""
    return HTMLResponse(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<body style="font-family:sans-serif;padding:32px 20px;max-width:420px;margin:auto">'
        '<h2 style="text-align:center">카카오로 로그인</h2>'
        '<form action="/api/auth/kakao/continue" method="get">'
        f'<input type="hidden" name="token" value="{html.escape(token)}">'
        '<label style="display:flex;gap:10px;align-items:flex-start;font-size:16px;margin:24px 0 8px">'
        '<input type="checkbox" name="agree" value="1" style="width:22px;height:22px;flex:none">'
        '<span>(선택) 쿠폰·이벤트 등 광고성 문자 수신에 동의합니다.</span></label>'
        '<p style="color:#777;font-size:13px;margin:0 0 24px">※ 임시 문구입니다. 정식 서비스 전에 개인정보 처리방침과 동의 문구를 확정해야 해요. '
        '동의하지 않아도 로그인할 수 있어요. 광고 문자는 21시~08시에는 보내지 않고, 문자 하단 안내로 언제든 수신을 거부할 수 있어요. '
        '로그인하면 카카오 계정의 성별·생일·휴대폰 번호(동의한 항목)를 함께 가져옵니다.</p>'
        '<button style="width:100%;font-size:18px;padding:12px;background:#fee500;border:0;border-radius:8px">'
        '카카오로 계속하기</button></form></body>')


@router.get("/kakao/continue")
async def kakao_continue(token: str, request: Request, agree: str = "", settings: Settings = Depends(get_settings)):
    """동의 선택을 세션에 기록하고 카카오 로그인으로 보낸다."""
    store = request.app.state.login_store
    s = store.by_token(token)
    if not s or store.status(s) != "scanned":
        return _page("로그인할 수 없어요", "만료되었거나 이미 사용된 QR입니다. 태블릿에서 새 QR을 받아 주세요.", 410)
    s.marketing_consent = agree == "1"
    if settings.supabase_enabled:  # Supabase Auth 가 카카오 로그인을 처리한다
        s.pkce_verifier, challenge = new_pkce_pair()
        return RedirectResponse(request.app.state.supabase.authorize_url(token, challenge), status_code=302)
    return RedirectResponse(request.app.state.kakao.authorize_url(token), status_code=302)


@router.get("/kakao/mock", include_in_schema=False)
async def kakao_mock(state: str, request: Request, settings: Settings = Depends(get_settings)):
    """키가 없을 때만 열리는 모의 카카오 로그인 화면."""
    if not request.app.state.kakao.mock or settings.supabase_enabled:
        raise HTTPException(404)
    return HTMLResponse(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<body style="font-family:sans-serif;text-align:center;padding:48px 20px"><h2>카카오 로그인 (모의)</h2>'
        '<form action="/api/auth/kakao/callback" method="get">'
        f'<input type="hidden" name="state" value="{html.escape(state)}">'
        '<input type="hidden" name="code" id="c"><input id="n" value="카카오손님" style="font-size:18px;padding:8px">'
        '<button style="font-size:18px;padding:8px 16px" onclick="c.value=\'mock-\'+n.value">로그인</button></form></body>')


@router.get("/kakao/callback")
async def kakao_callback(request: Request, state: str, code: str = "", error: str = "",
                         settings: Settings = Depends(get_settings)):
    app = request.app
    store = app.state.login_store
    s = store.by_token(state)  # state = 발급한 토큰. 불일치하면 CSRF로 보고 거부한다.
    if not s or store.status(s) != "scanned":
        return _page("로그인할 수 없어요", "만료되었거나 이미 사용된 QR입니다. 태블릿에서 새 QR을 받아 주세요.", 410)
    if error or not code:
        return _page("로그인이 취소되었어요", "다시 시도하려면 QR을 한 번 더 스캔해 주세요.", 400)
    try:
        profile = await app.state.kakao.fetch_profile(code)
    except KakaoError as e:
        return _page("카카오 로그인에 실패했어요", html.escape(str(e)), 502)
    member = app.state.members.set_marketing_consent(
        app.state.members.upsert_login(**profile)["id"], s.marketing_consent)
    access = tokens.issue(member["id"], settings.jwt_secret, settings.jwt_expire_minutes)
    if not store.complete(s, _public_member(member), access):
        return _page("로그인할 수 없어요", "QR이 만료되었습니다.", 410)
    return _page(f"{member['nickname']}님, 로그인 완료!", "태블릿 화면을 확인해 주세요. 이 창은 닫으셔도 됩니다.")


@router.get("/supabase/callback/{state}")
async def supabase_callback(state: str, request: Request, code: str = "", error: str = "",
                            settings: Settings = Depends(get_settings)):
    """Supabase 가 카카오 로그인 후 돌려보내는 주소. state(경로) = 발급한 QR 토큰."""
    app = request.app
    store = app.state.login_store
    s = store.by_token(state)
    if not settings.supabase_enabled or not s or store.status(s) != "scanned" or not s.pkce_verifier:
        return _page("로그인할 수 없어요", "만료되었거나 이미 사용된 QR입니다. 태블릿에서 새 QR을 받아 주세요.", 410)
    if error or not code:
        return _page("로그인이 취소되었어요", "다시 시도하려면 QR을 한 번 더 스캔해 주세요.", 400)
    verifier, s.pkce_verifier = s.pkce_verifier, None  # 코드 교환은 한 번만
    try:
        profile = await app.state.supabase.fetch_profile(code, verifier)
    except SupabaseAuthError as e:
        return _page("카카오 로그인에 실패했어요", html.escape(str(e)), 502)
    member = app.state.members.set_marketing_consent(
        app.state.members.upsert_login(**profile)["id"], s.marketing_consent)
    access = tokens.issue(member["id"], settings.jwt_secret, settings.jwt_expire_minutes)
    if not store.complete(s, _public_member(member), access):
        return _page("로그인할 수 없어요", "QR이 만료되었습니다.", 410)
    return _page(f"{member['nickname']}님, 로그인 완료!", "태블릿 화면을 확인해 주세요. 이 창은 닫으셔도 됩니다.")


@router.websocket("/ws/{secret}")
async def login_ws(ws: WebSocket, secret: str):
    """태블릿이 연결해 로그인 진행 상황을 실시간으로 받는다. 이벤트: scanned / logged_in / expired."""
    store = ws.app.state.login_store
    s = store.by_secret(secret)
    if not s:
        await ws.close(code=4404)
        return
    await ws.accept()
    queue = store.subscribe(s)
    try:
        await ws.send_json({"event": "status", "status": store.status(s), "remaining": int(store.remaining(s))})
        while True:
            status = store.status(s)
            if status == "logged_in":
                await ws.send_json(store.claim(s) or {"event": "status", "status": "claimed"})
                return
            if status == "expired":
                await ws.send_json({"event": "expired"})
                return
            try:  # 이벤트를 기다리되, 만료 시각이 되면 깨어나 expired 를 알린다.
                event = await asyncio.wait_for(queue.get(), timeout=store.remaining(s) + 0.05)
            except asyncio.TimeoutError:
                continue
            if event["event"] == "scanned":
                await ws.send_json(event)
    except Exception:  # 연결이 끊긴 경우: 정리만 하고 종료
        pass
    finally:
        store.unsubscribe(s, queue)
        try:
            await ws.close()
        except RuntimeError:
            pass
