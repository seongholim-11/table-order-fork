"""관리자 저장소의 짧은 응답 캐시: 같은 조회는 잠깐 재사용하고, 저장·발송 뒤에는 바로 최신 값을 다시 읽는다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import admin_repository as repo_mod


def make_backend(monkeypatch):
    """서버 대신 호출 횟수를 세는 가짜 api 를 끼운 ApiBackend."""
    monkeypatch.setattr(repo_mod, "CACHE_ON", True)
    calls = []

    def fake_get(path, token=None, **kw):
        calls.append(path)
        return {"n": len(calls)}

    monkeypatch.setattr(repo_mod.api, "get", fake_get)
    monkeypatch.setattr(repo_mod.api, "put", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(repo_mod.api, "post", lambda *a, **kw: {"ok": True})
    return repo_mod.ApiBackend("t"), calls


def test_same_read_is_reused_until_ttl(monkeypatch):
    backend, calls = make_backend(monkeypatch)
    assert backend.store() == backend.store()
    assert backend.customer_grade_rules() == backend.customer_grade_rules()
    assert len(calls) == 2  # 매장 정보·등급 기준을 각각 한 번만 읽었다

    clock = [1000.0]
    monkeypatch.setattr(repo_mod.time, "monotonic", lambda: clock[0])
    backend, calls = make_backend(monkeypatch)
    backend.stats({"repeat": 2})
    clock[0] += repo_mod.DATA_TTL + 1  # 보관 시간이 지나면 다시 읽는다
    backend.stats({"repeat": 2})
    assert len(calls) == 2


def test_different_params_are_not_mixed(monkeypatch):
    backend, calls = make_backend(monkeypatch)
    backend.stats({"repeat": 2})
    backend.stats({"repeat": 3})  # 등급 기준 미리보기가 다르면 다른 응답이다
    assert len(calls) == 2


def test_cached_value_is_a_copy(monkeypatch):
    backend, _ = make_backend(monkeypatch)
    first = backend.store()
    first["n"] = 999  # 화면이 값을 고쳐도
    assert backend.store()["n"] != 999  # 캐시는 그대로


def test_write_clears_cache(monkeypatch):
    backend, calls = make_backend(monkeypatch)
    backend.menus()
    backend.save_menu("a1", {"price": 1})
    backend.menus()
    assert len(calls) == 2  # 저장 뒤에는 바로 다시 읽는다
    backend.sms_balance()
    backend.sms_send(["휴면"], "hi")
    backend.sms_balance()
    assert len(calls) == 4  # 발송하면 잔액도 다시 읽는다


def test_sms_preview_is_reused_for_same_input(monkeypatch):
    backend, _ = make_backend(monkeypatch)
    posts = []
    monkeypatch.setattr(repo_mod.api, "post", lambda *a, **kw: posts.append(a) or {"ok": True})
    backend.sms_preview(["휴면"], "hello")
    backend.sms_preview(["휴면"], "hello")
    backend.sms_preview(["휴면"], "hello2")
    assert len(posts) == 2
