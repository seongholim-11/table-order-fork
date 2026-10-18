"""수용 1-2: 등급 집계·설정 조회·미리보기·기존 고객 API 호환성을 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.routers.admin import members as member_routes
from app.services.grades import KST, grade_counts
from tests.conftest import ADMIN, settings

BASE = "/admin/api/customers"
TODAY = datetime(2026, 10, 16, 12, tzinfo=KST)
EXPECTED = {"신규": 1, "재방문": 1, "단골": 1, "휴면": 1, "dormant_count": 1}


@pytest.fixture
def grade_client(client, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return TODAY.astimezone(tz) if tz else TODAY.replace(tzinfo=None)

    # 날짜가 바뀌어도 동일한 방문 기록으로 경계 조건을 검증한다.
    monkeypatch.setattr(member_routes, "datetime", FixedDatetime)
    for index, (visits, days) in enumerate(((1, 0), (3, 1), (7, 1), (10, 70))):
        member = client.app.state.members.upsert_login(f"grade-{index}", f"예시{index}")
        last = (TODAY - timedelta(days=days)).astimezone(timezone.utc).isoformat()
        client.app.state.db.run("UPDATE members SET visit_count=?, last_visit_at=? WHERE id=?",
                                (visits, last, member["id"]))
    return client


def test_each_grade_is_counted_once_and_dormancy_has_priority(grade_client):
    response = grade_client.get(f"{BASE}/grades", headers=ADMIN)
    assert response.status_code == 200
    assert response.json() == EXPECTED


def test_empty_database_returns_zero_for_every_grade(client):
    assert client.get(f"{BASE}/grades", headers=ADMIN).json() == {key: 0 for key in EXPECTED}


def test_rules_use_server_configuration_and_preview_never_writes(grade_client):
    # 미리보기는 이번 응답만 바꾸고 실제 방문 기록·기본 설정은 유지해야 한다.
    before = grade_client.app.state.members.all()
    response = grade_client.get(f"{BASE}/grades", headers=ADMIN, params={"regular": 10})
    assert response.json() == {**EXPECTED, "재방문": 2, "단골": 0}
    assert grade_client.app.state.members.all() == before
    assert grade_client.get(f"{BASE}/grades/rules", headers=ADMIN).json() == {
        "repeat": 2, "regular": 5, "dormant": 30,
    }
    assert grade_client.get(f"{BASE}/grades", headers=ADMIN).json() == EXPECTED


def test_environment_settings_are_used_unless_query_overrides_them():
    config = settings(grade_repeat_visits=3, grade_regular_visits=8, grade_dormant_days=90)
    with TestClient(create_app(config)) as client:
        assert client.get(f"{BASE}/grades/rules", headers=ADMIN).json() == {
            "repeat": 3, "regular": 8, "dormant": 90,
        }
        member = client.app.state.members.upsert_login("configured", "기준 확인")
        client.app.state.db.run("UPDATE members SET visit_count=6 WHERE id=?", (member["id"],))
        assert client.get(f"{BASE}/grades", headers=ADMIN).json()["재방문"] == 1
        assert client.get(f"{BASE}/grades", headers=ADMIN, params={"regular": 5}).json()["단골"] == 1


@pytest.mark.parametrize("query", [{"repeat": 1}, {"regular": 2}, {"dormant": 0},
                                  {"repeat": 5, "regular": 5}, {"repeat": 6, "regular": 5},
                                  {"regular": "잘못된 값"}])
def test_invalid_preview_is_rejected(client, query):
    assert client.get(f"{BASE}/grades", headers=ADMIN, params=query).status_code == 422


@pytest.mark.parametrize("path", [f"{BASE}/grades", f"{BASE}/grades/rules", BASE, "/admin/api/members"])
def test_customer_endpoints_require_admin_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_customer_alias_keeps_existing_member_response_and_opt_out(grade_client):
    old = grade_client.get("/admin/api/members", headers=ADMIN).json()
    assert grade_client.get(BASE, headers=ADMIN).json() == old
    for member, prefix in zip(old["members"][:2], (BASE, "/admin/api/members")):
        response = grade_client.post(f"{prefix}/{member['id']}/opt-out", headers=ADMIN)
        assert response.status_code == 200 and response.json() == {"ok": True}
        assert grade_client.app.state.members.get(member["id"])["opted_out"]
    assert grade_client.post(f"{BASE}/99999/opt-out", headers=ADMIN).status_code == 404
    assert grade_client.post(f"{BASE}/1/opt-out").status_code == 401


def test_dormancy_boundary_uses_kst_calendar_date():
    # 같은 UTC 날짜라도 KST 자정 전후라면 마지막 방문일이 하루 차이 난다.
    members = [
        {"visit_count": 7, "last_visit_at": "2026-08-17T14:59:59+00:00"},
        {"visit_count": 7, "last_visit_at": "2026-08-17T15:00:00+00:00"},
    ]
    counts = grade_counts(members, TODAY.date(), repeat=2, regular=5, dormant=60)
    assert counts == {"신규": 0, "재방문": 0, "단골": 1, "휴면": 1, "dormant_count": 1}
