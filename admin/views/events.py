"""이벤트 화면 (왼쪽 이벤트 목록 + 오른쪽 설정, 메뉴 관리와 같은 구성). 지금은 룰렛 하나.
"""

from html import escape

import pandas as pd
import streamlit as st

from admin.ui.widgets import page_head, sec_title
from admin_repository import ROULETTE_COLUMNS, ROULETTE_KINDS, ROULETTE_MAX_SLOTS, ROULETTE_MIN_SLOTS, CategoryError

ss = st.session_state
EVENTS = {"roulette": "🎰  행운의 룰렛"}


def select_event(event_id):
    ss["event_sel"] = event_id


def render_event_panel():
    """왼쪽: 이벤트 목록(클릭해서 선택)."""
    with st.container(border=True, key="mcat_panel"):
        st.html('<div class="mcat-title">🎉 이벤트</div>')
        for event_id, name in EVENTS.items():
            st.button(name, key=f"mcat_ev_{event_id}", width="stretch",
                      type="primary" if ss["event_sel"] == event_id else "secondary", on_click=select_event, args=(event_id,))
        st.html('<div class="mcat-hint">손님 첫 화면의 이벤트를 여기서 설정해요.</div>')


def wheel_preview(table, odds):
    """칸 색을 이은 원 미리보기 + 칸별 확률 목록 (손님 화면 룰렛은 칸이 모두 같은 크기이고 확률만 다르다)."""
    n = len(table)
    stops = ", ".join(f"{c if isinstance(c, str) and c.startswith('#') else '#888'} {i * 100 / n:.2f}% {(i + 1) * 100 / n:.2f}%"
                      for i, c in enumerate(table["색상"]))
    rows = "".join(f'<div class="bar-row"><span class="n">{escape(str(r["이모지"]))} {escape(str(r["칸 문구"]))}</span>'
                   f'<span class="t"><i style="width:{max(o, 1.5):.0f}%"></i></span><span class="c">{o:g}%</span></div>'
                   for (_, r), o in zip(table.iterrows(), odds))
    return (f'<div class="wheel-preview">'
            f'<div style="width:130px;height:130px;border-radius:50%;flex:none;border:4px solid rgba(128,128,128,.25);'
            f'background:conic-gradient({escape(stops)})"></div><div class="bars">{rows}</div></div>')


def render_roulette_panel(repo):
    old = repo.roulette_table()
    menu_names = list(repo.menus()["메뉴명"])
    st.html(f'<div class="mmenu-head"><b>🎰 행운의 룰렛</b><span>칸 {len(old)}개</span></div>')
    c_edit, c_prev = st.columns([3, 2], gap="medium")
    with c_edit:
        sec_title("칸 구성과 당첨 확률", "손님이 로그인하면 회원당 1회 돌릴 수 있어요")
        with st.container(key="events_table"):  # 표 높이는 화면 높이에 맞춰 CSS 가 정한다
            edited = _roulette_editor(old, menu_names)
        st.caption(f"칸은 {ROULETTE_MIN_SLOTS}~{ROULETTE_MAX_SLOTS}개. 표 아래 빈 줄에서 칸을 추가하고, 행을 선택해 지울 수 있어요.")
    new = edited.reset_index(drop=True)
    new["확률 가중치"] = pd.to_numeric(new["확률 가중치"], errors="coerce")
    with c_prev:
        sec_title("미리보기", "저장 전 표의 값 기준")
        shown = new.dropna(subset=["확률 가중치"]).fillna({"이모지": "", "칸 문구": ""})
        if shown.empty:
            st.caption("칸을 추가해 주세요.")
        else:
            st.html(wheel_preview(shown, repo.roulette_odds(shown)))
    _roulette_buttons(repo, old, new)


def _roulette_editor(old, menu_names):
    edited = st.data_editor(
        old, hide_index=True, width="stretch", num_rows="dynamic", height="stretch",
        key=f"roulette_editor_{ss['roulette_editor_v']}", column_order=ROULETTE_COLUMNS,
        column_config={
            "칸 문구": st.column_config.TextColumn(required=True, help="룰렛 칸에 보이는 첫 줄 (둘째 줄은 'N% 할인'·'서비스'가 자동으로 붙어요)"),
            "이모지": st.column_config.TextColumn(width="small"),
            "종류": st.column_config.SelectboxColumn(options=list(ROULETTE_KINDS.values()), required=True, width="small",
                                                   help="할인: 주문 전체 할인 / 서비스: 메뉴 1개를 무료로 담아 줘요"),
            "할인율(%)": st.column_config.NumberColumn(min_value=0, max_value=100, step=1, format="%d%%", help="종류가 '할인'일 때만 사용"),
            "서비스 메뉴": st.column_config.SelectboxColumn(options=menu_names, help="종류가 '서비스'일 때만 사용"),
            "색상": st.column_config.TextColumn(width="small", help="#RRGGBB 형식 (예: #f0556b)", default="#3ea0f5"),
            "확률 가중치": st.column_config.NumberColumn(min_value=0, step=1, default=1, required=True,
                                                      help="클수록 잘 나와요. 칸 가중치의 합 대비 비율이 당첨 확률 (0이면 당첨 안 됨)"),
            "당첨 안내문": st.column_config.TextColumn(help="당첨 후 보여줄 문구. 비우면 자동으로 만들어요"),
        })
    return edited


def _roulette_buttons(repo, old, new):
    dirty = not new.fillna("").astype(str).equals(old.fillna("").astype(str))
    c_save, c_undo, _ = st.columns([1, 1.3, 5])
    if c_undo.button("↩ 되돌리기", key="roulette_undo", width="stretch", disabled=not dirty,
                     help="저장하기 전의 변경을 모두 취소하고 저장된 값으로 돌립니다"):
        ss["roulette_editor_v"] += 1
        st.toast("저장하지 않은 변경을 되돌렸어요.", icon="↩️")
        st.rerun()
    if c_save.button("변경 저장", type="primary", key="roulette_save", width="stretch", disabled=not dirty):
        try:
            repo.save_roulette(new)
        except CategoryError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["roulette_editor_v"] += 1
            st.toast("룰렛 설정을 저장했습니다. 손님 화면에는 잠시 뒤 반영돼요.", icon="✅")
            st.rerun()


def page_events(repo):
    page_head("이벤트", "손님 화면에 보이는 이벤트를 설정하세요")
    ss.setdefault("roulette_editor_v", 0)
    ss.setdefault("event_sel", "roulette")
    left, right = st.columns([1.15, 3.6], gap="large")
    with left:
        render_event_panel()
    with right:
        if ss["event_sel"] == "roulette":
            render_roulette_panel(repo)
