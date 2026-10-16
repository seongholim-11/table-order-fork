"""고객 등급 화면.
"""

import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head
from admin_repository import DEFAULT_RULE, GRADES

ss = st.session_state


def reset_rule():
    ss["grade_rule"] = dict(DEFAULT_RULE)
    for key in ("rule_repeat", "rule_regular", "rule_dormant"):
        ss.pop(key, None)


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
    rule = ss["grade_rule"]  # 기준값은 세션에 저장돼 있어서 다른 하위 메뉴로 옮겨도 유지된다
    if sub == "등급 분류 기준":
        st.caption("등급 분류 기준 (임시 — 추가 정의 필요)")
        c1, c2, c3 = st.columns(3)
        rule["repeat"] = c1.number_input("재방문: 방문 횟수 ≥", 2, 50, rule["repeat"], key="rule_repeat")
        rule["regular"] = c2.number_input("단골: 방문 횟수 ≥", rule["repeat"] + 1, 100, max(rule["regular"], rule["repeat"] + 1), key="rule_regular")
        rule["dormant"] = c3.number_input("휴면: 마지막 방문 후 N일 이상", 7, 365, rule["dormant"], key="rule_dormant")
        st.button("↩ 기본값으로 되돌리기", key="rule_reset", disabled=rule == DEFAULT_RULE, on_click=reset_rule,
                  help="등급 분류 기준을 처음 값으로 돌립니다")
        st.html(grade_rule_table(rule))
        st.caption("위에서부터 차례로 확인해 먼저 맞는 등급이 됩니다. 이 값은 화면에서 미리 보는 용도이고 서버에는 저장되지 않아요.")
    else:  # 고객 목록
        cust = repo.members(rule)
        kpi_row(*[kpi(f"{g} 고객", int((cust["등급"] == g).sum()), "명") for g in GRADES])
        pick = st.multiselect("등급 필터", GRADES, default=GRADES)
        with st.container(key="customers_table"):
            st.dataframe(cust[cust["등급"].isin(pick)], hide_index=True, width="stretch", height="stretch")
