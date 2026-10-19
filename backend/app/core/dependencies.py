"""관리자 인증 등 공통 의존성."""

from fastapi import Depends, Header, HTTPException, Request

from app.core.settings import Settings, get_settings
from app.services import tokens


def require_admin(
    request: Request,
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """관리자 인증. 사장님 로그인(Supabase 토큰)을 우선 지원하고, 개발용 ADMIN_TOKEN 도 받는다.

    운영(APP_ENV=prod)에서 Supabase 가 설정돼 있으면 ADMIN_TOKEN 은 더 이상 받지 않는다.
    Supabase 로 들어온 사장님의 id 는 request.state.owner_id 에 담아 챗봇 등이 쓴다.
    """
    legacy_allowed = not (settings.app_env == "prod" and settings.supabase_enabled)
    if legacy_allowed and authorization == f"Bearer {settings.admin_token}":
        return
    token = authorization.removeprefix("Bearer ").strip()
    if token and settings.supabase_enabled:
        owner_id = request.app.state.owners.owner_id_from_token(token, request.app.state.supabase)
        if owner_id:
            request.state.owner_id = owner_id
            return
    raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")


def current_member(request: Request, authorization: str = Header(default=""),
                   settings: Settings = Depends(get_settings)) -> dict:
    """로그인한 손님. 'Authorization: Bearer <JWT>' 를 검증한다."""
    member_id = tokens.decode(authorization.removeprefix("Bearer ").strip(), settings.jwt_secret)
    member = request.app.state.members.get(member_id) if member_id else None
    if not member:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return member


def optional_member(request: Request, authorization: str = Header(default=""),
                    settings: Settings = Depends(get_settings)) -> dict | None:
    """로그인 여부와 상관없이 쓰는 API(주문 등)에서 회원이면 회원 정보를 붙인다. 잘못된 토큰은 비회원으로 본다."""
    member_id = tokens.decode(authorization.removeprefix("Bearer ").strip(), settings.jwt_secret)
    return request.app.state.members.get(member_id) if member_id else None
