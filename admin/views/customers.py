"""고객 등급 화면.
"""

import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head
from admin_repository import DEFAULT_RULE, GRADES
from shared.api import ApiError, ApiUnavailable

ss = st.session_state


def reset_rule():
    # 서버 설정이 바뀐 경우에도 하드코딩된 값 대신 실제 기본 기준으로 돌아간다.
    ss["grade_rule"] = dict(ss.get("customer_rule_defaults", DEFAULT_RULE))
    # 조건표의 복원 미리보기는 다른 화면이 사용하는 저장 기준과 따로 관리한다.
    ss["grade_rule_preview"] = dict(ss["grade_rule"])
    for key in ("rule_repeat", "rule_regular", "rule_dormant"):
        ss.pop(key, None)
    ss["grade_inputs_changed"] = False


def reset_rule_inputs():
    """입력칸만 초기화한다. 아래 조건표와 DB의 적용 기준은 바꾸지 않는다."""
    for name, value in DEFAULT_RULE.items():
        ss[f"rule_{name}"] = value
    ss["grade_inputs_changed"] = False


def restore_rule():
    """마지막 저장값과 구분해 조건 미리보기와 입력칸을 초기 기준으로 돌린다."""
    ss["grade_rule_preview"] = dict(DEFAULT_RULE)
    reset_rule_inputs()


def preview_rule():
    """입력 변경만 기록한다. 다른 입력칸과 저장 전 조건표·집계는 바꾸지 않는다."""
    ss["grade_inputs_changed"] = True


def save_rule(repo):
    """실패하면 미리보기를 그대로 두고, 성공 응답을 받은 뒤에만 저장 상태로 바꾼다."""
    rule = {name: ss[f"rule_{name}"] for name in ("repeat", "regular", "dormant")}
    # 사장님이 지정한 숫자를 자동 보정하지 않고, 저장할 수 없는 조합만 안내한다.
    if rule["regular"] <= rule["repeat"]:
        ss["grade_save_error"] = "단골 기준은 재방문 기준보다 크게 지정해 주세요. 입력한 숫자는 그대로 유지됩니다."
        return
    try:
        saved = repo.save_customer_grade_rules(rule)
    except (ApiError, ApiUnavailable):
        ss["grade_save_error"] = "기준을 저장하지 못했어요. 서버 연결과 입력값을 확인한 뒤 다시 저장해 주세요."
        return
    ss["customer_rule_defaults"] = dict(saved)
    ss["grade_rule"] = dict(saved)
    ss["grade_rule_preview"] = dict(saved)
    ss["grade_save_success"] = True
    ss.pop("grade_save_error", None)
    ss["grade_inputs_changed"] = False
    # 이전 기준으로 만든 문자 후보·대상 선택을 새 기준에 섞지 않는다.
    for key in ("ai_candidates", "ai_picked", "sms_excluded"):
        ss.pop(key, None)


def _render_grade_counts(repo, rule):
    """목록 화면과 기준 미리보기가 같은 백엔드 집계 결과를 표시한다."""
    counts = repo.customer_grades(rule)
    kpi_row(*[kpi(f"{grade} 고객", counts[grade], "명") for grade in GRADES])


def grade_rule_table(rule):
    """현재 기준값을 '순서 · 등급 · 조건' 표로 보여준다 (휴면이 가장 먼저 판정된다)."""
    rows = [
        ("1", "휴면", f"마지막 방문 후 <b>{rule['dormant']}일</b> 이상 지남", "방문 횟수와 상관없이 우선 적용"),
        ("2", "단골", f"방문 <b>{rule['regular']}회</b> 이상", ""),
        ("3", "재방문", f"방문 <b>{rule['repeat']}~{rule['regular'] - 1}회</b>", ""),
        ("4", "신규", f"방문 <b>{rule['repeat'] - 1}회</b> 이하", "위에 해당하지 않는 나머지"),
    ]
    th = "padding:8px 12px;white-space:nowrap;text-align:left;border-bottom:2px solid rgba(128,128,128,.35);font-size:13px;opacity:.75"
    td = "padding:8px 12px;border-bottom:1px solid rgba(128,128,128,.2);font-size:14px"
    body = "".join(
        f'<tr><td style="{td};width:48px;text-align:center">{n}</td><td style="{td};white-space:nowrap"><b>{g}</b></td>'
        f'<td style="{td}">{cond}</td><td style="{td};opacity:.7;font-size:13px">{note}</td></tr>'
        for n, g, cond, note in rows
    )
    return (f'<table style="width:100%;border-collapse:collapse;margin:12px 0 4px"><thead><tr>'
            f'<th style="{th};text-align:center">순서</th><th style="{th}">등급</th><th style="{th}">조건</th><th style="{th}">비고</th>'
            f'</tr></thead><tbody>{body}</tbody></table>')


def page_customers(repo, sub="고객 목록"):
    """고객 목록 / 등급 분류 기준은 사이드바 하위 메뉴에서 고른다 (admin/app.py 의 SUBPAGES)."""
    page_head("고객 등급", "방문 이력으로 고객을 신규·재방문·단골·휴면으로 나눠요")
    defaults = repo.customer_grade_rules()
    if ("customer_rule_defaults" not in ss or ss.get("customer_rule_source") != repo.source
            or ss["customer_rule_defaults"] != defaults):
        # 서버의 기본 기준이 바뀐 경우에도 새 정책을 반영하고, 그 외에는 미리보기를 유지한다.
        ss["customer_rule_defaults"] = dict(defaults)
        ss["customer_rule_source"] = repo.source
        reset_rule()
    ss["customer_rule_defaults"] = dict(defaults)
    # 복원 미리보기는 기준 화면에만 표시하고 고객 목록은 실제 저장 기준으로 분류한다.
    rule = ss.setdefault("grade_rule_preview", dict(defaults)) if sub == "등급 분류 기준" else defaults
    if sub == "등급 분류 기준":
        st.caption("숫자를 수정한 뒤 기준 저장을 눌러 적용해 주세요. 저장 전에는 아래 조건과 고객 수가 바뀌지 않아요.")
        if ss.pop("grade_save_success", False):
            st.success("등급 기준을 저장했어요. 고객 목록·통계·단골 추천·문자 대상에 함께 적용됩니다.")
        if ss.get("grade_save_error"):
            st.error(ss["grade_save_error"])
        # 입력값과 적용 기준을 분리해 저장 전에는 조건표가 바뀌지 않도록 한다.
        for name, value in rule.items():
            ss.setdefault(f"rule_{name}", value)
        c1, c2, c3 = st.columns(3)
        c1.number_input("재방문: 방문 횟수 ≥", min_value=2, step=1, key="rule_repeat", on_change=preview_rule)
        c2.number_input("단골: 방문 횟수 ≥", min_value=3,
                        step=1, key="rule_regular", on_change=preview_rule)
        c3.number_input("휴면: 마지막 방문 후 N일 이상", min_value=1, step=1, key="rule_dormant", on_change=preview_rule)
        # 두 버튼을 바로 옆에 두고, 서버 연결 시 같은 값도 다시 저장·복원할 수 있게 한다.
        with st.container(horizontal=True, gap="small"):
            st.button("기준 저장", key="rule_save", type="primary", disabled=repo.source != "api",
                      on_click=save_rule, args=(repo,))
            st.button("↩ 기본값으로 되돌리기", key="rule_reset", on_click=restore_rule)
        if ss.get("grade_inputs_changed") or rule != defaults:
            st.warning("저장하지 않은 미리보기입니다. 단골 추천과 문자 대상의 실제 기준은 저장 전 값이 유지됩니다.")
        else:
            st.info("현재 적용 중인 기준입니다. 저장한 기준은 새로고침하거나 서버를 다시 켜도 유지됩니다.")
        if repo.source != "api":
            st.caption("더미 모드에서는 미리보기만 가능해요. 실제 기준 저장은 서버 연결 후 사용할 수 있어요.")
        st.html(grade_rule_table(rule))
        st.caption("위에서부터 차례로 확인해 먼저 맞는 등급이 됩니다. 숫자만 바꿔서는 서버에 저장되지 않아요.")
        st.caption("현재 미리보기 기준의 고객 수")
        _render_grade_counts(repo, rule)
    else:  # 고객 목록
        cust = repo.members(rule)
        _render_grade_counts(repo, rule)
        pick = st.multiselect("등급 필터", GRADES, default=GRADES)
        with st.container(key="customers_table"):
            st.dataframe(cust[cust["등급"].isin(pick)], hide_index=True, width="stretch", height="stretch")
