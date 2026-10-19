"""Supabase Auth 로 카카오 로그인을 처리한다 (PKCE). docs/정식_구현_계획.md 4장 가이드 참고.

흐름: 휴대폰을 Supabase /auth/v1/authorize?provider=kakao 로 보냄 → 카카오 로그인 →
Supabase 가 redirect_to(우리 서버)로 ?code= 와 함께 돌려보냄 → code + code_verifier 로 사용자 정보를 받는다.
code_verifier 는 서버(로그인 세션)만 알고 있어서, 코드가 새어도 다른 사람이 교환할 수 없다.
"""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from app.core.settings import Settings
from app.services.kakao import KakaoError, fetch_account


class SupabaseAuthError(Exception):
    pass


def new_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) — challenge 는 verifier 의 SHA-256 을 base64url(패딩 없음)로 인코딩."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class SupabaseAuthClient:
    def __init__(self, settings: Settings):
        self.s = settings

    @property
    def base(self) -> str:
        return self.s.supabase_url.rstrip("/") + "/auth/v1"

    def sign_in_password(self, email: str, password: str) -> dict:
        """사장님 이메일/비밀번호 로그인. 성공하면 {access_token, user_id, email} 을 돌려준다."""
        try:
            r = httpx.post(f"{self.base}/token", params={"grant_type": "password"},
                           headers={"apikey": self.s.supabase_anon_key}, json={"email": email, "password": password},
                           timeout=10)
        except httpx.HTTPError as e:
            raise SupabaseAuthError("Supabase 에 연결할 수 없습니다.") from e
        data = r.json() if r.status_code == 200 else {}
        user = data.get("user") or {}
        if not data.get("access_token") or not user.get("id"):
            raise SupabaseAuthError("이메일 또는 비밀번호가 올바르지 않습니다.")
        return {"access_token": data["access_token"], "user_id": user["id"], "email": user.get("email", email)}

    def get_user_id(self, access_token: str) -> str | None:
        """Supabase 가 발급한 액세스 토큰이 유효하면 사용자 id(uuid 문자열), 아니면 None."""
        try:
            r = httpx.get(f"{self.base}/user", headers={"apikey": self.s.supabase_anon_key,
                                                         "Authorization": f"Bearer {access_token}"}, timeout=10)
        except httpx.HTTPError:
            return None
        return (r.json().get("id") if r.status_code == 200 else None) or None

    def callback_url(self, token: str) -> str:
        # 쿼리스트링 대신 경로에 토큰을 넣는다: Supabase Redirect URLs 의 `/**` 와일드카드로 허용된다.
        return f"{self.s.public_base_url}/api/auth/supabase/callback/{token}"

    def authorize_url(self, token: str, code_challenge: str) -> str:
        return f"{self.base}/authorize?" + urlencode({
            "provider": "kakao", "redirect_to": self.callback_url(token), "scopes": self.s.kakao_scopes,
            "code_challenge": code_challenge, "code_challenge_method": "s256"})

    async def fetch_profile(self, code: str, code_verifier: str) -> dict:
        """인가 코드를 Supabase 세션으로 교환하고 {kakao_id, nickname, gender, birthday, birth_year, phone} 를 돌려준다.

        성별·생일·출생연도·휴대폰 번호는 Supabase 사용자 정보에 없으므로, 세션에 담겨 오는 카카오 액세스 토큰
        (provider_token)으로 카카오 /v2/user/me 를 한 번 더 호출해 채운다. 실패하거나 동의하지 않은 항목은 비워 둔다."""
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(f"{self.base}/token", params={"grant_type": "pkce"},
                                headers={"apikey": self.s.supabase_anon_key},
                                json={"auth_code": code, "code_verifier": code_verifier})
        if r.status_code != 200:
            raise SupabaseAuthError("Supabase 로그인 확인에 실패했습니다.")
        session = r.json()
        user = session.get("user") or {}
        if not user.get("id"):
            raise SupabaseAuthError("Supabase 사용자 정보를 받지 못했습니다.")
        meta = user.get("user_metadata") or {}
        nickname = meta.get("name") or meta.get("full_name") or meta.get("preferred_username") or "손님"
        # members.kakao_id 칸에는 Supabase 사용자 id(auth.users.id)를 저장한다.
        extra = {"gender": None, "birthday": None, "birth_year": None, "phone": None}
        if session.get("provider_token"):
            try:
                kakao = await fetch_account(session["provider_token"])
                extra = {k: kakao[k] for k in extra}
                if kakao["nickname"] != "손님":
                    nickname = kakao["nickname"]  # 카카오 이름(name)을 우선 사용
            except (KakaoError, httpx.HTTPError):
                pass  # 추가 정보를 못 받아도 로그인은 계속한다
        return {"kakao_id": f"sb:{user['id']}", "nickname": nickname, **extra}
