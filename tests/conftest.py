import pytest
import streamlit as st


@pytest.fixture(autouse=True)
def fresh_streamlit_cache():
    """서버 데이터는 10초 캐시되므로(운영에서는 의도된 동작) 테스트마다 비운다."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.fixture(autouse=True)
def token_login_screen(monkeypatch):
    """기존 테스트는 토큰 입력 화면을 거친다. (ADMIN_SKIP_TOKEN 기본값은 '입력 생략')"""
    monkeypatch.setenv("ADMIN_SKIP_TOKEN", "0")


@pytest.fixture(autouse=True)
def not_dev_env(monkeypatch):
    """내 PC 의 backend/.env 에 APP_ENV=dev 가 있어도 기존 테스트가 자동 로그인에 영향받지 않게 prod 로 고정한다."""
    monkeypatch.setenv("APP_ENV", "prod")
