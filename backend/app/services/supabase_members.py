"""로그인한 회원을 Supabase members 테이블에도 쌓는다 (RPC upsert_member_login 호출).

서버 전용 service_role 키로 호출한다. 키가 없으면 아무것도 하지 않고, 실패해도 로그인은 막지 않는다.
"""

import logging

import httpx

from app.core.settings import Settings

log = logging.getLogger(__name__)


async def sync_member(settings: Settings, profile: dict) -> None:
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return
    key = settings.supabase_service_role_key
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.post(
                settings.supabase_url.rstrip("/") + "/rest/v1/rpc/upsert_member_login",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                json={"p_kakao_id": profile["kakao_id"], "p_nickname": profile["nickname"],
                      "p_gender": profile.get("gender"), "p_birthday": profile.get("birthday")})
        if r.status_code >= 300:
            log.warning("Supabase members 저장 실패: %s %s", r.status_code, r.text[:200])
    except httpx.HTTPError as e:
        log.warning("Supabase members 저장 실패: %s", e)
