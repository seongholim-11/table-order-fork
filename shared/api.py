"""FastAPI 서버 호출 공통 함수 (user·admin 공용).

서버에 닿지 않으면 ApiUnavailable, 서버가 4xx/5xx 로 답하면 ApiError 를 던진다.
테스트에서는 set_client(TestClient(app)) 로 실제 서버 없이 앱을 연결할 수 있다.
"""

import os
from pathlib import Path

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
_client: httpx.Client | None = None


def is_dev() -> bool:
    """APP_ENV=dev 인지 확인한다. 개발 편의(자동 로그인)는 이 값이 정확히 'dev' 일 때만 켜진다.

    화면(Streamlit)은 backend/.env 를 자동으로 읽지 않으므로, 셸 환경변수가 없으면 backend/.env 의 APP_ENV 줄을 직접 읽는다.
    둘 다 없거나 dev 가 아니면(운영·미설정) False 라서 로그인 우회가 절대 켜지지 않는다.
    """
    value = os.getenv("APP_ENV")
    if value is None:
        env_file = Path(__file__).resolve().parent.parent / "backend" / ".env"
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, _, val = line.partition("=")
                if key.strip() == "APP_ENV":
                    value = val.split("#")[0].strip().strip("\"'")
        except OSError:
            pass  # .env 가 없으면 미설정으로 본다
    return (value or "").strip().lower() == "dev"


class ApiError(Exception):
    def __init__(self, status: int, detail):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


class ApiUnavailable(Exception):
    """서버에 연결할 수 없음 (꺼져 있거나 주소가 틀림)."""


def set_client(client: httpx.Client | None) -> None:
    global _client
    _client = client


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=API_URL, timeout=5)
    return _client


def request(method: str, path: str, token: str | None = None, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = _http().request(method, path, headers=headers, **kw)
    except httpx.HTTPError as e:
        raise ApiUnavailable(str(e)) from e
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise ApiError(r.status_code, detail)
    return r.json() if r.content else None


def get(path: str, token: str | None = None, **kw):
    return request("GET", path, token, **kw)


def post(path: str, token: str | None = None, **kw):
    return request("POST", path, token, **kw)


def put(path: str, token: str | None = None, **kw):
    return request("PUT", path, token, **kw)


def patch(path: str, token: str | None = None, **kw):
    return request("PATCH", path, token, **kw)


def delete(path: str, token: str | None = None, **kw):
    return request("DELETE", path, token, **kw)
