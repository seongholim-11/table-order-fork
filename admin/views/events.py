"""이벤트 화면 (왼쪽 이벤트 목록 + 오른쪽 설정, 메뉴 관리와 같은 구성). 지금은 룰렛 하나.
"""

from html import escape

import pandas as pd
import streamlit as st

from admin.ui.widgets import page_head, sec_title
from admin_repository import ALL_MENU_LABEL, ROULETTE_COLUMNS, ROULETTE_KINDS, ROULETTE_MAX_SLOTS, ROULETTE_MIN_SLOTS, CategoryError

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
    rows = "".join(f'<div class="bar-row"><span class="n">{escape(str(r["이모지"]))} {escape(str(r["표시 문구"]))}</span>'
                   f'<span class="t"><i style="width:{max(o, 1.5):.0f}%"></i></span><span class="c">{o:g}%</span></div>'
                   for (_, r), o in zip(table.iterrows(), odds))
    return (f'<div class="wheel-preview">'
            f'<div style="width:130px;height:130px;border-radius:50%;flex:none;border:4px solid rgba(128,128,128,.25);'
            f'background:conic-gradient({escape(stops)})"></div><div class="bars">{rows}</div></div>')


def render_roulette_panel(repo):
    old = repo.roulette_table()
    menu_choices = repo.roulette_menu_choices()
    menu_names = [choice["label"] for choice in menu_choices]
    menu_emojis = {choice["label"]: choice["emoji"] for choice in menu_choices}
    st.html(f'<div class="mmenu-head"><b>🎰 행운의 룰렛</b><span>칸 {len(old)}개</span></div>')
    # 편집 영역을 미리보기와 좌우로 나누면 선택 상자가 너무 좁아진다.
    # 전체 너비로 옵션을 먼저 보여 주고 미리보기는 아래에 배치해 각 문구가 잘리지 않게 한다.
    sec_title("칸 구성과 당첨 확률", "손님이 로그인하면 회원당 1회 돌릴 수 있어요")
    with st.container(key="events_table"):
        edited = _roulette_editor(old, menu_names)
    st.caption(f"칸은 {ROULETTE_MIN_SLOTS}~{ROULETTE_MAX_SLOTS}개. 메뉴와 종류는 한 번 눌러 목록에서 고를 수 있어요.")
    new = edited.reset_index(drop=True)
    new["확률 가중치"] = pd.to_numeric(new["확률 가중치"], errors="coerce")
    probability_total = int(new["확률 가중치"].fillna(0).sum())
    if probability_total == 100:
        st.success("확률 합계 100%")
    else:
        st.warning(f"확률 합계 {probability_total}% · 저장하려면 100%로 맞춰 주세요.")

    sec_title("미리보기", "저장 전 선택값 기준")
    shown = new.dropna(subset=["확률 가중치"]).copy()
    service_rows = shown["종류"] == ROULETTE_KINDS["free"]
    shown["이모지"] = "🎟️"
    shown.loc[service_rows, "이모지"] = shown.loc[service_rows, "서비스 메뉴"].map(menu_emojis).fillna("🍴")
    shown["표시 문구"] = shown["할인율(%)"].map(lambda value: f"{int(value)}% 할인")
    shown.loc[service_rows, "표시 문구"] = shown.loc[service_rows, "서비스 메뉴"].fillna("메뉴 선택").map(
        lambda value: value.split("] ", 1)[-1])
    if shown.empty:
        st.caption("칸을 추가해 주세요.")
    else:
        st.html(wheel_preview(shown, repo.roulette_odds(shown)))
    _roulette_buttons(repo, new)


def _roulette_editor(old, menu_names):
    """표 셀 대신 바로 누를 수 있는 선택 상자를 사용해 두 번 클릭 문제를 없앤다."""
    version = ss["roulette_editor_v"]
    draft_key = f"roulette_draft_{version}"
    if draft_key not in ss:
        ss[draft_key] = [{**row, "_id": f"{version}-{index}"} for index, row in enumerate(old.to_dict("records"))]

    rows, delete_id = [], None
    for row in ss[draft_key]:
        row_id = row["_id"]
        with st.container(border=True):
            menu_col, kind_col, rate_col, weight_col, color_col, delete_col = st.columns([3, 1.4, 1.4, 1.4, 1, 1.2])
            menu_index = menu_names.index(row["서비스 메뉴"]) if row.get("서비스 메뉴") in menu_names else None
            menu = menu_col.selectbox("서비스 메뉴", menu_names, index=menu_index, placeholder="메뉴 선택",
                                      key=f"roulette_menu_{row_id}")
            # 전체 메뉴는 할인 전용 옵션이므로 선택 즉시 종류를 할인으로 고정한다.
            selected_kind = ROULETTE_KINDS["discount"] if menu == ALL_MENU_LABEL else row.get("종류", "서비스")
            # 같은 키의 위젯은 index보다 이전 선택값을 우선하므로 세션 값도 함께 바꾼다.
            if menu == ALL_MENU_LABEL:
                ss[f"roulette_kind_{row_id}"] = selected_kind
            kind = kind_col.selectbox("종류", list(ROULETTE_KINDS.values()),
                                      index=list(ROULETTE_KINDS.values()).index(selected_kind),
                                      key=f"roulette_kind_{row_id}", disabled=menu == ALL_MENU_LABEL)
            rates = [5, 10, 15, 20]
            current_rate = int(row.get("할인율(%)", 5))
            rate = rate_col.selectbox("할인율", rates, index=rates.index(current_rate) if current_rate in rates else 0,
                                      format_func=lambda value: f"{value}%", key=f"roulette_rate_{row_id}",
                                      disabled=kind != ROULETTE_KINDS["discount"])
            current_weight = int(row.get("확률 가중치", 0))
            # 목록에서 고르는 대신 1% 단위 숫자를 직접 입력한다.
            weight = weight_col.number_input("확률 (%)", min_value=0, max_value=100,
                                             value=current_weight, step=1, format="%d",
                                             key=f"roulette_weight_{row_id}")
            color = color_col.color_picker("색상", value=row.get("색상", "#3ea0f5"), key=f"roulette_color_{row_id}")
            if delete_col.button("삭제", key=f"roulette_delete_{row_id}", use_container_width=True):
                delete_id = row_id
            rows.append({"서비스 메뉴": menu, "종류": kind, "할인율(%)": rate,
                         "확률 가중치": weight, "색상": color, "_id": row_id})

    ss[draft_key] = rows
    if delete_id is not None:
        ss[draft_key] = [row for row in rows if row["_id"] != delete_id]
        st.rerun()
    if st.button("＋ 룰렛 칸 추가", key=f"roulette_add_{version}", disabled=len(rows) >= ROULETTE_MAX_SLOTS):
        next_id = f"{version}-new-{len(rows)}"
        ss[draft_key].append({"서비스 메뉴": None, "종류": "서비스", "할인율(%)": 5,
                              "확률 가중치": 0.0, "색상": "#3ea0f5", "_id": next_id})
        st.rerun()
    return pd.DataFrame([{key: row.get(key) for key in ROULETTE_COLUMNS} for row in rows], columns=ROULETTE_COLUMNS)


def _roulette_buttons(repo, new):
    # DummyBackend에서는 관리자 화면 세션에만 저장한다. 손님 Frontend에 자동 반영하는 시점·캐시 정책은
    # 팀 협의 후 같은 repository 메서드의 실제 API 연결부에서 결정할 수 있도록 화면에서는 저장소만 호출한다.
    if st.button("저장하기", type="primary", key="roulette_save", use_container_width=True):
        try:
            repo.save_roulette(new)
        except CategoryError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss.pop(f"roulette_draft_{ss['roulette_editor_v']}", None)
            ss["roulette_editor_v"] += 1
            st.toast("룰렛 더미 설정을 저장했습니다.", icon="✅")
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
