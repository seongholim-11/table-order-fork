"""환경 변수에서 설정을 읽는다."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"  # prod 이면 기본 비밀값(change-me)으로는 기동하지 않는다
    database_url: str = "sqlite:///./app.db"
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:8502"]
    admin_token: str = "change-me"
    dev_test_button: bool = False  # 포크·DB 연결 흐름을 확인할 때만 여는 개발 전용 기능

    store_name: str = "역전할머니맥주"
    store_branch: str = "홍대점"
    store_slogan: str = "옛날 그 맛 그대로, 시원한 생맥주 한 잔!"
    store_tables: int = 30

    # 고객 등급 기준 (임시값, 정책 확정 후 조정)
    grade_repeat_visits: int = 2
    grade_regular_visits: int = 5
    grade_dormant_days: int = 30  # 휴면: 마지막 방문 후 30일 이상

    # QR 로그인 / 카카오 (docs/정식_구현_계획.md 1장)
    public_base_url: str = "http://localhost:8000"  # 휴대폰이 접속할 서버 주소 (QR에 들어감)
    kakao_rest_api_key: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/api/auth/kakao/callback"
    # 로그인 때 자동으로 받아올 카카오 동의항목(scope). 카카오 콘솔에 설정되지 않은 항목이 있으면 KOE205 오류가 난다.
    kakao_scopes: str = "name gender birthday birthyear phone_number"
    # Supabase Auth 로 카카오 로그인 처리 (URL 과 anon 키가 모두 있으면 직접 카카오 호출 대신 이 방식을 쓴다)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # 서버 전용. 현재 로그인·DB 흐름에는 쓰지 않음
    jwt_secret: str = "change-me"
    login_ttl_seconds: int = 180
    jwt_expire_minutes: int = 720

    # 문자 발송 / 솔라피 (docs/정식_구현_계획.md 2장)
    solapi_api_key: str = ""
    solapi_api_secret: str = ""
    solapi_sender_number: str = ""  # 솔라피에 등록된 발신번호
    sms_opt_out_number: str = ""  # 광고 문자 하단의 무료수신거부 번호
    sms_monthly_limit: int = 50
    lms_monthly_limit: int = 10
    sms_dry_run: bool = True  # True면 솔라피를 호출하지 않고 로그만 남긴다

    # AI 문자 후보 · 외부 정보 (docs/todo/TODO_성호.md 3번)
    gemini_api_key: str = ""  # 비어 있으면 AI 대신 템플릿 문구를 쓴다
    gemini_model: str = "gemini-2.5-flash"
    # AI 챗봇 (docs/todo/TODO_성호.md 4번). 관리자 인증 전까지 모든 대화방의 주인(auth.users 의 uuid)으로 쓴다
    chat_owner_id: str = ""
    seoul_openapi_key: str = ""  # 서울 열린데이터광장 인증키. 비어 있으면 행사 문구는 비워 둔다
    store_gu: str = "마포구"  # 행사를 찾을 자치구 (매장 위치)
    store_lat: float = 37.5563  # 날씨를 조회할 매장 위치 (홍대)
    store_lon: float = 126.9236

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
