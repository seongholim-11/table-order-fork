"""카카오 로그인 클라이언트. REST API 키가 없으면 모의(mock) 모드로 동작한다.

모의 모드: 카카오 대신 서버가 만든 간단한 로그인 페이지(/api/auth/kakao/mock)를 보여주고,
code 를 "mock-닉네임" 형태로 받아 그대로 프로필로 쓴다. 실제 키를 넣으면 자동으로 실제 모드가 된다.
"""

from urllib.parse import quote, urlencode

import httpx

from app.core.settings import Settings

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoError(Exception):
    pass


def normalize_phone(raw: str | None) -> str | None:
    """카카오 phone_number("+82 10-1234-5678")를 010-1234-5678 형태로. 휴대폰 번호가 아니면 None."""
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if digits.startswith("82"):
        digits = "0" + digits[2:]
    if len(digits) not in (10, 11) or not digits.startswith("01"):
        return None
    return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


def parse_account(account: dict) -> dict:
    """카카오 kakao_account 에서 동의항목으로 받은 값만 골라낸다. 동의하지 않았거나 없는 값은 None."""
    year = str(account.get("birthyear") or "")
    return {"gender": account.get("gender"), "birthday": account.get("birthday") or None,
            "birth_year": int(year) if year.isdigit() else None,
            "phone": normalize_phone(account.get("phone_number"))}


async def fetch_account(access_token: str) -> dict:
    """카카오 액세스 토큰으로 /v2/user/me 를 호출해 {kakao_id, nickname, gender, birthday, birth_year, phone} 를 돌려준다."""
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"})
    if r.status_code != 200:
        raise KakaoError("카카오 사용자 정보를 가져오지 못했습니다.")
    body = r.json()
    account = body.get("kakao_account", {})
    return {"kakao_id": str(body["id"]), "nickname": (account.get("profile") or {}).get("nickname") or "손님",
            **parse_account(account)}


class KakaoClient:
    def __init__(self, settings: Settings):
        self.s = settings

    @property
    def mock(self) -> bool:
        return not self.s.kakao_rest_api_key

    def authorize_url(self, state: str) -> str:
        if self.mock:
            return f"{self.s.public_base_url}/api/auth/kakao/mock?state={quote(state)}"
        return AUTHORIZE_URL + "?" + urlencode({
            "client_id": self.s.kakao_rest_api_key, "redirect_uri": self.s.kakao_redirect_uri,
            "response_type": "code", "state": state, "scope": ",".join(self.s.kakao_scopes.split())})

    async def fetch_profile(self, code: str) -> dict:
        """인가 코드로 사용자 프로필을 가져온다: {kakao_id, nickname, gender, birthday, birth_year, phone}."""
        if self.mock:
            if not code.startswith("mock-"):
                raise KakaoError("모의 로그인 코드가 올바르지 않습니다.")
            nickname = code.removeprefix("mock-") or "카카오"
            return {"kakao_id": f"mock:{nickname}", "nickname": nickname, "gender": None, "birthday": None,
                    "birth_year": None, "phone": None}
        async with httpx.AsyncClient(timeout=10) as http:
            data = {"grant_type": "authorization_code", "client_id": self.s.kakao_rest_api_key,
                    "redirect_uri": self.s.kakao_redirect_uri, "code": code}
            if self.s.kakao_client_secret:
                data["client_secret"] = self.s.kakao_client_secret
            r = await http.post(TOKEN_URL, data=data)
            if r.status_code != 200:
                raise KakaoError("카카오 토큰 발급에 실패했습니다.")
            token = r.json()["access_token"]
        return await fetch_account(token)
