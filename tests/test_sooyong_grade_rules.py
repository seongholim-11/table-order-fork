"""수용 5: 미리보기·저장·복원·새 화면·서버 오류를 실제 화면에서 검증한다."""

import pytest
from streamlit.testing.v1 import AppTest

from test_sooyong_customer_grades import ROOT, open_rules, server
from shared.api import ApiError, ApiUnavailable


@pytest.mark.parametrize(("regular", "visits"), [(8, 7), (3, 4)])
def test_restore_preview_stays_in_rules_until_save_and_sms_targets_match(server, monkeypatch, regular, visits):
    """복원은 기준 화면에서만 미리 보고, 다른 화면과 문자 대상은 저장값을 사용한다."""
    saved = {"repeat": 2, "regular": regular, "dormant": 30}
    server.put("/admin/api/customers/grades/rules", headers={"Authorization": "Bearer admin-secret"}, json=saved)
    db = server.app.state.db
    db.run("UPDATE members SET visit_count=?, phone=?, marketing_consent=1", (visits, "01000000000"))
    members_before = server.app.state.members.all()
    screen = open_rules(monkeypatch)
    screen.button(key="rule_reset").click().run()
    assert not screen.exception
    assert screen.number_input(key="rule_regular").value == 5
    assert screen.session_state["grade_rule"] == saved
    assert screen.session_state["grade_rule_preview"] == {"repeat": 2, "regular": 5, "dormant": 30}
    assert screen.session_state["repo"].customer_grade_rules() == saved

    # 고객 목록·대시보드·추천으로 이동해도 저장 전 미리보기는 적용하지 않는다.
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert screen.dataframe[0].value.iloc[0]["등급"] == ("단골" if visits >= regular else "재방문")
    for group, sub in (("대시보드", "고객 분석"), ("마케팅", "AI 추천"), ("마케팅", "AI 문자")):
        screen.sidebar.radio(key=f"nav_sub_{group}").set_value(sub).run()
        assert not screen.exception and screen.session_state["grade_rule"] == saved
    screen.multiselect(key="sms_grades").set_value(["단골"]).run()
    expected = len(server.app.state.sms.targets(["단골"]))
    assert len(screen.dataframe[0].value) == expected == int(visits >= regular)
    assert any(f"발송 대상 {expected}명" in caption.value for caption in screen.caption)

    # 돌아와 복원 미리보기를 저장한 뒤에만 고객 분류와 실제 문자 대상이 함께 바뀐다.
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    assert screen.number_input(key="rule_regular").value == 5
    screen.button(key="rule_save").click().run()
    assert not screen.exception and screen.session_state["repo"].customer_grade_rules()["regular"] == 5
    screen.sidebar.radio(key="nav_sub_마케팅").set_value("AI 문자").run()
    screen.multiselect(key="sms_grades").set_value(["단골"]).run()
    expected = len(server.app.state.sms.targets(["단골"]))
    assert not screen.exception and len(screen.dataframe[0].value) == expected == int(visits >= 5)
    assert any(f"발송 대상 {expected}명" in caption.value for caption in screen.caption)
    assert server.app.state.members.all() == members_before


def test_plus_and_minus_inputs_leave_conditions_counts_and_database_unchanged_until_save(server, monkeypatch):
    """세 입력칸의 증감이 조건표나 고객 분류에 자동 반영되지 않는지 확인한다."""
    screen = open_rules(monkeypatch)
    original = dict(screen.session_state["grade_rule"])
    original_html = [element.value for element in screen.get("html")]
    original_counts = screen.session_state["repo"].customer_grades()
    original_members = server.app.state.members.all()
    for name, value in (("repeat", 3), ("repeat", 4), ("repeat", 3),
                        ("regular", 9), ("regular", 6), ("dormant", 45), ("dormant", 31)):
        screen.number_input(key=f"rule_{name}").set_value(value).run()
        assert not screen.exception
        assert screen.session_state["grade_rule"] == original
        assert [element.value for element in screen.get("html")] == original_html
        assert screen.session_state["repo"].customer_grade_rules() == original
        assert screen.session_state["repo"].customer_grades() == original_counts
        assert server.app.state.members.all() == original_members
    screen.button(key="rule_save").click().run()
    saved = {"repeat": 3, "regular": 6, "dormant": 31}
    assert not screen.exception
    assert screen.session_state["grade_rule"] == saved
    assert screen.session_state["repo"].customer_grade_rules() == saved
    assert screen.session_state["repo"].customer_grades()["단골"] == 1
    assert [screen.number_input(key=f"rule_{name}").value for name in ("repeat", "regular", "dormant")] == [3, 6, 31]


def test_save_keeps_inputs_and_restore_previews_original_defaults_without_writing(server, monkeypatch):
    """저장 후 조건 유지와 기본값 복원을 구분하고, 복원만으로 DB가 바뀌지 않게 한다."""
    screen = open_rules(monkeypatch)
    for name, value in (("repeat", 3), ("regular", 6), ("dormant", 45)):
        screen.number_input(key=f"rule_{name}").set_value(value).run()
    saved = {"repeat": 3, "regular": 6, "dormant": 45}
    screen.button(key="rule_save").click().run()
    assert not screen.exception
    for name, value in saved.items():
        assert screen.number_input(key=f"rule_{name}").value == value
    assert screen.session_state["grade_rule"] == saved
    assert screen.session_state["repo"].customer_grade_rules() == saved
    # 단순 재실행에도 입력칸과 저장 기준이 일치해야 한다.
    screen.run()
    assert screen.session_state["grade_rule"] == saved
    table = "\n".join(element.value for element in screen.get("html"))
    assert "방문 <b>6회</b> 이상" in table and "<b>45일</b> 이상" in table
    # 저장 직후에도 마지막 저장값 대신 초기 기준으로 복원할 수 있어야 한다.
    assert not screen.button(key="rule_reset").disabled
    screen.button(key="rule_reset").click().run()
    assert not screen.exception
    for name, default in (("repeat", 2), ("regular", 5), ("dormant", 30)):
        assert screen.number_input(key=f"rule_{name}").value == default
    assert screen.session_state["grade_rule_preview"] == {"repeat": 2, "regular": 5, "dormant": 30}
    assert screen.session_state["grade_rule"] == saved
    assert screen.session_state["repo"].customer_grade_rules() == saved
    table = "\n".join(element.value for element in screen.get("html"))
    assert "방문 <b>5회</b> 이상" in table and "<b>30일</b> 이상" in table
    screen.run()
    assert screen.session_state["grade_rule_preview"] == {"repeat": 2, "regular": 5, "dormant": 30}
    assert screen.session_state["grade_rule"] == saved
    # 이미 초기 기준이어도 여러 번 복원할 수 있고, 반복 클릭으로 DB를 변경하지 않는다.
    for _ in range(3):
        assert not screen.button(key="rule_reset").disabled
        screen.button(key="rule_reset").click().run()
        assert not screen.exception
        assert screen.session_state["grade_rule_preview"] == {"repeat": 2, "regular": 5, "dormant": 30}
        assert screen.session_state["grade_rule"] == saved
        assert screen.session_state["repo"].customer_grade_rules() == saved
    # 초기 기준을 실제 DB에 적용하는 시점은 기존과 같이 기준 저장을 눌렀을 때다.
    screen.button(key="rule_save").click().run()
    assert not screen.exception
    assert screen.session_state["repo"].customer_grade_rules() == {"repeat": 2, "regular": 5, "dormant": 30}


def test_preview_is_not_saved_then_save_survives_new_screen_and_reset(server, monkeypatch):
    screen = open_rules(monkeypatch)
    assert not screen.button(key="rule_save").disabled
    assert not screen.button(key="rule_reset").proto.help
    screen.number_input(key="rule_regular").set_value(5).run()
    assert screen.warning and not screen.button(key="rule_save").disabled
    assert server.get("/admin/api/customers/grades/rules", headers={"Authorization": "Bearer admin-secret"}).json()["regular"] == 8
    screen.button(key="rule_save").click().run()
    assert not screen.exception and screen.success
    assert screen.session_state["repo"].customer_grade_rules()["regular"] == 5
    assert not screen.button(key="rule_save").disabled
    # 같은 기본값을 반복 저장해도 버튼은 활성 상태이고 DB 기준은 일관되게 유지된다.
    for _ in range(3):
        screen.button(key="rule_save").click().run()
        assert not screen.exception and not screen.button(key="rule_save").disabled
        assert screen.session_state["repo"].customer_grade_rules() == {"repeat": 2, "regular": 5, "dormant": 30}
    screen.number_input(key="rule_regular").set_value(9).run()
    screen.button(key="rule_reset").click().run()
    assert screen.number_input(key="rule_regular").value == 5
    fresh = open_rules(monkeypatch)
    assert fresh.number_input(key="rule_regular").value == 5
    fresh.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert fresh.dataframe[0].value.iloc[0]["등급"] == "단골"


@pytest.mark.parametrize("failure", [ApiUnavailable("테스트 연결 오류"), ApiError(500, "테스트 저장 오류")])
def test_save_failure_preserves_preview_and_saved_rule(server, monkeypatch, failure):
    screen = open_rules(monkeypatch)
    screen.number_input(key="rule_regular").set_value(5).run()
    def fail(rule):
        raise failure
    monkeypatch.setattr(screen.session_state["repo"], "save_customer_grade_rules", fail)
    screen.button(key="rule_save").click().run()
    assert not screen.exception and screen.error
    assert screen.number_input(key="rule_regular").value == 5
    assert screen.session_state["repo"].customer_grade_rules()["regular"] == 8


def test_external_save_updates_existing_session_on_other_pages(server, monkeypatch):
    screen = open_rules(monkeypatch)
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("한눈에 보기").run()
    rule = {"repeat": 2, "regular": 9, "dormant": 45}
    server.put("/admin/api/customers/grades/rules", headers={"Authorization": "Bearer admin-secret"}, json=rule)
    screen.run()
    assert not screen.exception and screen.session_state["grade_rule"] == rule
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    assert screen.number_input(key="rule_regular").value == 9
    assert screen.number_input(key="rule_dormant").value == 45


def test_increasing_repeat_never_changes_regular_and_invalid_save_keeps_entered_numbers(server, monkeypatch):
    # 다른 입력칸은 자동 변경하지 않고, 잘못된 조합의 저장만 막는다.
    screen = open_rules(monkeypatch)
    original = dict(screen.session_state["grade_rule"])
    screen.number_input(key="rule_repeat").set_value(10).run()
    assert not screen.exception
    assert screen.number_input(key="rule_regular").value == 8
    assert screen.number_input(key="rule_dormant").value == 30
    screen.button(key="rule_save").click().run()
    assert not screen.exception and screen.error
    assert screen.number_input(key="rule_repeat").value == 10
    assert screen.number_input(key="rule_regular").value == 8
    assert screen.session_state["grade_rule"] == original
    assert screen.session_state["repo"].customer_grade_rules() == original
    screen.number_input(key="rule_regular").set_value(11).run()
    screen.button(key="rule_save").click().run()
    assert not screen.exception
    assert screen.session_state["repo"].customer_grade_rules() == {"repeat": 10, "regular": 11, "dormant": 30}
    assert screen.number_input(key="rule_repeat").value == 10
    assert screen.number_input(key="rule_regular").value == 11


def test_sequential_single_field_saves_preserve_other_saved_values(server, monkeypatch):
    """재방문 저장 후 휴면만 바꿔도 재방문 기준이 기본값으로 돌아가지 않아야 한다."""
    screen = open_rules(monkeypatch)
    screen.number_input(key="rule_repeat").set_value(3).run()
    screen.button(key="rule_save").click().run()
    assert screen.number_input(key="rule_repeat").value == 3
    screen.number_input(key="rule_dormant").set_value(45).run()
    screen.button(key="rule_save").click().run()
    assert not screen.exception
    assert screen.session_state["repo"].customer_grade_rules() == {"repeat": 3, "regular": 8, "dormant": 45}
    assert screen.session_state["grade_rule"] == {"repeat": 3, "regular": 8, "dormant": 45}


def test_repeated_save_without_new_edits_preserves_custom_rule(server, monkeypatch):
    screen = open_rules(monkeypatch)
    screen.number_input(key="rule_regular").set_value(9).run()
    screen.button(key="rule_save").click().run()
    saved = {"repeat": 2, "regular": 9, "dormant": 30}
    for _ in range(3):
        screen.button(key="rule_save").click().run()
        assert not screen.exception and not screen.button(key="rule_save").disabled
        assert screen.session_state["repo"].customer_grade_rules() == saved
        assert screen.number_input(key="rule_regular").value == 9


def test_dummy_mode_does_not_pretend_to_save_to_database(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_SKIP_TOKEN", "1")
    monkeypatch.setenv("APP_ENV", "dev")
    screen = AppTest.from_file(str(ROOT / "admin/app.py"), default_timeout=30).run()
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    screen.number_input(key="rule_regular").set_value(8).run()
    assert not screen.exception and screen.button(key="rule_save").disabled
    assert any("더미 모드에서는 미리보기만" in caption.value for caption in screen.caption)
