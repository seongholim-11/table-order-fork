from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.factory import create_app


def make(ttl=180):
    s = Settings(database_url="sqlite:///:memory:", login_ttl_seconds=ttl, kakao_rest_api_key="",
                 public_base_url="http://t", jwt_secret="x" * 32, _env_file=None)
    return create_app(s)


def scan_and_login(c, token, nick="홍길동", agree=False):
    r = c.get(f"/api/auth/kakao/start?token={token}")
    assert r.status_code == 200 and "광고성 문자 수신" in r.text  # 카카오로 가기 전에 동의(선택)를 받는다
    r = c.get("/api/auth/kakao/continue", params={"token": token, **({"agree": "1"} if agree else {})},
              follow_redirects=False)
    assert r.status_code == 302 and "/kakao/mock" in r.headers["location"]
    return c.get("/api/auth/kakao/callback", params={"state": token, "code": f"mock-{nick}"})


def test_full_flow_with_websocket():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 12}).json()
        assert q["qr_url"] == f"http://t/api/auth/kakao/start?token={q['token']}" and q["expires_in"] == 180
        with c.websocket_connect(f"/api/auth/ws/{q['secret']}") as ws:
            assert ws.receive_json()["status"] == "waiting"
            c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False)
            assert ws.receive_json() == {"event": "scanned"}
            r = c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-홍길동"})
            assert r.status_code == 200 and "홍길동" in r.text
            done = ws.receive_json()
        assert done["event"] == "logged_in" and done["member"]["nickname"] == "홍길동"
        me = c.get("/api/members/me", headers={"Authorization": f"Bearer {done['access_token']}"})
        assert me.status_code == 200 and me.json()["visit_count"] == 1


def test_token_is_single_use_and_rescan_rejected():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        assert scan_and_login(c, q["token"]).status_code == 200
        assert c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False).status_code == 410
        again = c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-다른사람"})
        assert again.status_code == 410


def test_callback_requires_scan_and_valid_state():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        # 스캔 없이 콜백, 알 수 없는 state 모두 거부
        assert c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-a"}).status_code == 410
        assert c.get("/api/auth/kakao/callback", params={"state": "nope", "code": "mock-a"}).status_code == 410
        assert c.get("/api/auth/kakao/start?token=nope", follow_redirects=False).status_code == 404


def test_secret_is_separate_from_qr_token():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        scan_and_login(c, q["token"])
        assert c.get(f"/api/auth/qr/{q['token']}").status_code == 404  # QR 값으로는 결과를 못 본다
        first = c.get(f"/api/auth/qr/{q['secret']}").json()
        assert first["event"] == "logged_in" and first["access_token"]
        assert c.get(f"/api/auth/qr/{q['secret']}").json()["status"] == "claimed"  # 한 번만 전달


def test_expiry_over_websocket_and_polling():
    with TestClient(make(ttl=1)) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        with c.websocket_connect(f"/api/auth/ws/{q['secret']}") as ws:
            ws.receive_json()
            assert ws.receive_json() == {"event": "expired"}
        assert c.get(f"/api/auth/qr/{q['secret']}").json()["status"] == "expired"
        assert c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False).status_code == 410


def test_unknown_websocket_secret_rejected():
    with TestClient(make()) as c:
        with pytest.raises(Exception):
            with c.websocket_connect("/api/auth/ws/nope"):
                pass


def test_returning_member_and_consent_at_login():
    with TestClient(make()) as c:
        tokens = []
        for agree in (False, True):
            q = c.post("/api/auth/qr", json={"table_no": 1}).json()
            scan_and_login(c, q["token"], "단골", agree=agree)
            tokens.append(c.get(f"/api/auth/qr/{q['secret']}").json()["access_token"])
        h = {"Authorization": f"Bearer {tokens[1]}"}
        me = c.get("/api/members/me", headers=h).json()
        assert me["visit_count"] == 2 and me["marketing_consent"] is True  # 두 번째 로그인에서 동의
        assert c.patch("/api/members/me", headers=h, json={"phone": "010-1234-5678"}).status_code == 405  # 직접 입력 기능 없음
        assert c.get("/api/members/me").status_code == 401
        assert c.get("/api/members/me", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_consent_defaults_to_no_and_latest_choice_wins():
    with TestClient(make()) as c:
        def once(agree):
            q = c.post("/api/auth/qr", json={"table_no": 1}).json()
            scan_and_login(c, q["token"], "손님", agree=agree)
            h = {"Authorization": f"Bearer {c.get(f'/api/auth/qr/{q['secret']}').json()['access_token']}"}
            return c.get("/api/members/me", headers=h).json()["marketing_consent"]
        assert once(False) is False and once(True) is True and once(False) is False


def test_continue_requires_scanned_session():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        assert c.get("/api/auth/kakao/continue", params={"token": q["token"]}, follow_redirects=False).status_code == 410
        assert c.get("/api/auth/kakao/continue", params={"token": "nope"}, follow_redirects=False).status_code == 410


def test_kakao_account_parsing():
    from app.services.kakao import normalize_phone, parse_account
    assert normalize_phone("+82 10-1234-5678") == "010-1234-5678" and normalize_phone("010 123 4567") == "010-123-4567"
    assert normalize_phone("+82 2-123-4567") is None and normalize_phone(None) is None
    assert parse_account({"gender": "female", "birthday": "0312", "birthyear": "1995", "phone_number": "+82 10-1234-5678"}) == {
        "gender": "female", "birthday": "0312", "birth_year": 1995, "phone": "010-1234-5678"}
    assert parse_account({}) == {"gender": None, "birthday": None, "birth_year": None, "phone": None}


def test_login_profile_fills_member_without_overwriting_with_blanks():
    from app.stores.members import MemberStore
    store = MemberStore()
    store.upsert_login("k1", "가", gender="female", birthday="0312", birth_year=1995, phone="010-1234-5678")
    m = store.upsert_login("k1", "가")  # 이후 로그인에서 동의 안 한 값은 기존 값을 지우지 않는다
    assert (m["gender"], m["birth_year"], m["phone"], m["visit_count"]) == ("female", 1995, "010-1234-5678", 2)


def test_mock_page_hidden_when_real_keys_set():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="k", _env_file=None)
    with TestClient(create_app(s)) as c:
        assert c.get("/api/auth/kakao/mock?state=x").status_code == 404
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        c.get(f"/api/auth/kakao/start?token={q['token']}")
        loc = c.get("/api/auth/kakao/continue", params={"token": q["token"]}, follow_redirects=False).headers["location"]
        qs = parse_qs(urlparse(loc).query)
        assert loc.startswith("https://kauth.kakao.com/oauth/authorize") and qs["state"] == [q["token"]]
        assert set(qs["scope"][0].split(",")) >= {"gender", "birthday", "birthyear", "phone_number"}


# --- Supabase Auth (카카오 로그인을 Supabase 가 처리) ---
def make_supabase():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, supabase_url="https://abc.supabase.co", supabase_anon_key="anon", _env_file=None)
    return create_app(s)


def test_supabase_pkce_pair():
    import base64, hashlib
    from app.services.supabase_auth import new_pkce_pair
    verifier, challenge = new_pkce_pair()
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_supabase_flow(monkeypatch):
    app = make_supabase()
    seen = {}

    async def fake_profile(code, verifier):
        seen.update(code=code, verifier=verifier)
        return {"kakao_id": "sb:uuid-1", "nickname": "슈파", "gender": None, "birthday": None}

    monkeypatch.setattr(app.state.supabase, "fetch_profile", fake_profile)
    with TestClient(app) as c:
        q = c.post("/api/auth/qr", json={"table_no": 3}).json()
        c.get(f"/api/auth/kakao/start?token={q['token']}")
        r = c.get("/api/auth/kakao/continue", params={"token": q["token"]}, follow_redirects=False)
        loc = urlparse(r.headers["location"])
        assert r.status_code == 302 and loc.netloc == "abc.supabase.co" and loc.path == "/auth/v1/authorize"
        params = parse_qs(loc.query)
        assert "gender" in params["scopes"][0].split() and params["provider"] == ["kakao"] and params["code_challenge_method"] == ["s256"]
        assert params["redirect_to"] == [f"http://t/api/auth/supabase/callback/{q['token']}"]
        assert c.get("/api/auth/kakao/mock", params={"state": q["token"]}).status_code == 404  # 모의 화면 꺼짐
        ok = c.get(f"/api/auth/supabase/callback/{q['token']}", params={"code": "abc"})
        assert ok.status_code == 200 and "슈파" in ok.text and seen["code"] == "abc" and seen["verifier"]
        done = c.get(f"/api/auth/qr/{q['secret']}").json()
        assert done["event"] == "logged_in" and done["member"]["nickname"] == "슈파"
        # 같은 QR 의 콜백 재사용 거부
        assert c.get(f"/api/auth/supabase/callback/{q['token']}", params={"code": "abc"}).status_code == 410


def test_supabase_callback_rejects_unscanned_error_and_unknown_state():
    with TestClient(make_supabase()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        assert c.get(f"/api/auth/supabase/callback/{q['token']}", params={"code": "x"}).status_code == 410  # 스캔 전
        assert c.get("/api/auth/supabase/callback/nope", params={"code": "x"}).status_code == 410
        c.get(f"/api/auth/kakao/start?token={q['token']}")
        c.get("/api/auth/kakao/continue", params={"token": q["token"]}, follow_redirects=False)
        assert c.get(f"/api/auth/supabase/callback/{q['token']}", params={"error": "access_denied"}).status_code == 400


def test_regenerate_discards_previous_session():
    with TestClient(make()) as c:
        old = c.post("/api/auth/qr", json={"table_no": 1}).json()
        new = c.post("/api/auth/qr", json={"table_no": 1, "previous_secret": old["secret"]}).json()
        assert new["token"] != old["token"] and new["secret"] != old["secret"]
        assert c.get(f"/api/auth/qr/{old['secret']}").status_code == 404
        assert c.get(f"/api/auth/kakao/start?token={old['token']}", follow_redirects=False).status_code == 404
        assert c.get(f"/api/auth/qr/{new['secret']}").json()["status"] == "waiting"


def test_regenerate_keeps_completed_login():
    with TestClient(make()) as c:
        old = c.post("/api/auth/qr", json={"table_no": 1}).json()
        scan_and_login(c, old["token"])
        c.post("/api/auth/qr", json={"table_no": 1, "previous_secret": old["secret"]})
        assert c.get(f"/api/auth/qr/{old['secret']}").json()["event"] == "logged_in"
