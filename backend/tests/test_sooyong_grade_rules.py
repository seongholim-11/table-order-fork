"""수용 5: 기준을 저장하고 다시 읽어도 모든 소비자가 같은 정책을 쓰는지 확인한다."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services.grades import KST
from app.stores.grade_rules import GradeRuleStore
from tests.conftest import ADMIN, settings
from tests.test_sooyong_regular_notes import prepare, notes

URL = "/admin/api/customers/grades/rules"
RULE = {"repeat": 3, "regular": 8, "dormant": 45}


def test_save_survives_new_app_and_database_connection(tmp_path):
    # 메모리 공유나 설정 변경만으로 통과하지 않도록 별도 연결에서 영구 저장을 검증한다.
    config = settings(database_url="sqlite:///" + (tmp_path / "grades.db").as_posix(), grade_regular_visits=10)
    with TestClient(create_app(config)) as first:
        assert first.put(URL, headers=ADMIN, json=RULE).json() == RULE
        row = first.app.state.db.one("SELECT updated_at FROM app_settings WHERE key='grade_rule'")
        assert row["updated_at"]
    with TestClient(create_app(config)) as second:
        assert second.get(URL, headers=ADMIN).json() == RULE
        assert second.app.state.db.one("SELECT COUNT(*) AS n FROM app_settings WHERE key='grade_rule'")["n"] == 1
        second.put(URL, headers=ADMIN, json={**RULE, "regular": 9})
        assert second.app.state.db.one("SELECT updated_at FROM app_settings WHERE key='grade_rule'")["updated_at"] != row["updated_at"]


def test_missing_saved_rule_uses_environment_without_inserting_a_row():
    with TestClient(create_app(settings(grade_repeat_visits=4, grade_regular_visits=9, grade_dormant_days=70))) as client:
        assert client.get(URL, headers=ADMIN).json() == {"repeat": 4, "regular": 9, "dormant": 70}
        assert GradeRuleStore(client.app.state.db).get() is None


def test_saved_rule_changes_counts_and_query_preview_has_priority_without_writing(client):
    member = client.app.state.members.upsert_login("saved-rule", "기준 검증 회원")
    client.app.state.db.run("UPDATE members SET visit_count=7 WHERE id=?", (member["id"],))
    assert client.get("/admin/api/customers/grades", headers=ADMIN).json()["단골"] == 1
    assert client.put(URL, headers=ADMIN, json=RULE).status_code == 200
    before = client.app.state.db.one("SELECT * FROM app_settings WHERE key='grade_rule'")
    assert client.get("/admin/api/customers/grades", headers=ADMIN).json()["재방문"] == 1
    assert client.get("/admin/api/customers/grades", headers=ADMIN, params={"regular": 5}).json()["단골"] == 1
    for path in ("/admin/api/members", "/admin/api/customers"):
        assert client.get(path, headers=ADMIN).json()["members"][0]["grade"] == "재방문"
        assert client.get(path, headers=ADMIN, params={"regular": 5}).json()["members"][0]["grade"] == "단골"
    assert client.app.state.db.one("SELECT * FROM app_settings WHERE key='grade_rule'") == before
    assert client.app.state.members.get(member["id"])["visit_count"] == 7


@pytest.mark.parametrize("bad", [
    {**RULE, "regular": 3}, {**RULE, "repeat": 9}, {**RULE, "repeat": 1},
    {**RULE, "regular": 2}, {**RULE, "dormant": 0}, {**RULE, "regular": "8"},
    {**RULE, "repeat": True}, {**RULE, "regular": 8.5}, {"regular": 8},
    {**RULE, "extra": "미지원"}, {**RULE, "dormant": None},
])
def test_invalid_save_returns_422_and_preserves_previous_rule(client, bad):
    client.put(URL, headers=ADMIN, json=RULE)
    before = client.app.state.db.one("SELECT * FROM app_settings WHERE key='grade_rule'")
    assert client.put(URL, headers=ADMIN, json=bad).status_code == 422
    assert client.app.state.db.one("SELECT * FROM app_settings WHERE key='grade_rule'") == before


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_save_requires_admin_token(client, headers):
    assert client.put(URL, headers=headers, json=RULE).status_code == 401
    assert GradeRuleStore(client.app.state.db).get() is None


def test_regular_threshold_changes_grade_and_sms_but_keeps_repeat_customer_care(client):
    member = prepare(client, visits=3)
    client.app.state.db.run("UPDATE members SET phone=?, marketing_consent=1 WHERE id=?", ("01000000000", member["id"]))
    assert notes(client)[0]["grade"] == "재방문"
    assert client.app.state.sms.targets(["단골"]) == []
    lower = {"repeat": 2, "regular": 3, "dormant": 30}
    client.put(URL, headers=ADMIN, json=lower)
    assert notes(client)[0]["member_id"] == member["id"]
    assert client.app.state.sms.targets(["단골"])[0]["id"] == member["id"]
    assert client.app.state.sms_candidates.summary()["pool"] == {"단골": 1}
    client.put(URL, headers=ADMIN, json=RULE)
    assert notes(client)[0]["grade"] == "재방문"
    assert client.app.state.sms.targets(["단골"]) == []
    assert client.app.state.sms_candidates.summary()["pool"] == {"재방문": 1}


def test_dormancy_and_repeat_threshold_reach_stats_and_sms_without_editing_members(client):
    member = prepare(client, visits=5, days=0)
    last = (datetime.now(KST) - timedelta(days=40)).isoformat()
    client.app.state.db.run("UPDATE members SET last_visit_at=?, phone=?, marketing_consent=1 WHERE id=?",
                           (last, "01000000000", member["id"]))
    original = client.app.state.members.all()
    assert client.get("/admin/api/stats", headers=ADMIN).json()["returning_customers"] == 0
    client.put(URL, headers=ADMIN, json={"repeat": 6, "regular": 8, "dormant": 45})
    stats = client.get("/admin/api/stats", headers=ADMIN).json()
    assert stats["new_customers"] == 1 and stats["returning_customers"] == 0
    insights = client.get("/admin/api/stats/insights", headers=ADMIN).json()
    assert insights["customer_grades"]["신규"] == 1
    assert client.app.state.sms.targets(["신규"])[0]["id"] == member["id"]
    assert client.app.state.sms_candidates.summary()["pool"] == {"신규": 1}
    assert client.get("/admin/api/stats", headers=ADMIN, params={"repeat": 2}).json()["returning_customers"] == 1
    assert client.app.state.members.all() == original
