"""메뉴 관리 화면 (카테고리 + 메뉴 등록·편집).
"""

import streamlit as st

from admin.ui.widgets import bars, page_head, panel
from admin_repository import COLOR_PRESETS, ICON_DEFAULT, SPICY_LABELS, CategoryError

ss = st.session_state


def select_category(category_id):
    ss["menu_cat"] = category_id


def render_category_panel(repo, cats):
    """왼쪽: 카테고리 목록(클릭해서 선택) + 추가·수정·삭제."""
    with st.container(border=True, key="mcat_panel"):
        st.html('<div class="mcat-title">📂 카테고리</div>')
        if not cats:
            st.html('<div class="mcat-hint">아직 카테고리가 없어요. 아래에서 추가해 보세요.</div>')
        for c in cats:
            st.button(f"{c['icon']}  {c['name']}  ({c['menu_count']})", key=f"mcat_{c['id']}", width="stretch",
                      type="primary" if ss["menu_cat"] == c["id"] else "secondary",
                      on_click=select_category, args=(c["id"],))

        with st.expander("＋ 카테고리 추가"):
            with st.form("cat_add_form", clear_on_submit=True):
                name = st.text_input("이름", placeholder="예: 세트 메뉴")
                icon = st.text_input("아이콘 (이모지)", value=ICON_DEFAULT, max_chars=4)
                color = st.selectbox("색상", list(COLOR_PRESETS))
                if st.form_submit_button("추가", type="primary", width="stretch"):
                    try:
                        ss["menu_cat"] = repo.add_category(name, icon, color)
                    except CategoryError as e:
                        st.error(str(e))
                    else:
                        st.toast("카테고리를 추가했어요. 이제 메뉴를 등록해 보세요.", icon="✅")
                        st.rerun()

        selected = next((c for c in cats if c["id"] == ss["menu_cat"]), None)
        if selected:
            with st.expander(f"✏️ '{selected['name']}' 수정·삭제"):
                with st.form(f"cat_edit_form_{selected['id']}"):
                    name = st.text_input("이름", value=selected["name"])
                    icon = st.text_input("아이콘 (이모지)", value=selected["icon"], max_chars=4)
                    color = st.selectbox("색상", ["(그대로)"] + list(COLOR_PRESETS))
                    f_undo = st.form_submit_button("↩ 되돌리기", width="stretch",
                                                   help="입력한 값을 지우고 저장된 값으로 돌립니다")
                    if f_undo:
                        st.rerun()
                    if st.form_submit_button("수정 저장", width="stretch"):
                        try:
                            repo.update_category(selected["id"], name, icon, None if color == "(그대로)" else color)
                        except CategoryError as e:
                            st.error(str(e))
                        else:
                            st.toast("카테고리를 수정했어요.", icon="✅")
                            st.rerun()
                if selected["menu_count"]:
                    st.caption(f"메뉴 {selected['menu_count']}개가 있어서 삭제할 수 없어요. 메뉴를 먼저 정리해 주세요.")
                else:
                    sure = st.checkbox("정말 삭제할게요", key=f"cat_del_ok_{selected['id']}")
                    if st.button("🗑 카테고리 삭제", disabled=not sure, width="stretch", key="cat_delete"):
                        try:
                            repo.delete_category(selected["id"])
                        except CategoryError as e:
                            st.error(str(e))
                        else:
                            ss["menu_cat"] = None
                            st.toast("카테고리를 삭제했어요.", icon="🗑")
                            st.rerun()


def render_menu_register_form(repo, category):
    with st.form(f"menu_add_form_{category['id']}", clear_on_submit=True):
        c1, c2 = st.columns([3, 1.4])
        name = c1.text_input("메뉴 이름 *", placeholder="예: 매운 닭볶음탕")
        price = c2.number_input("가격 *", min_value=0, step=500, value=10000)
        desc = st.text_input("설명", placeholder="손님 화면에 보이는 한 줄 설명")
        image = st.text_input("이미지 URL", placeholder="https://...")
        c3, c4, c5, c6 = st.columns(4)
        spicy = c3.selectbox("매운 정도", list(SPICY_LABELS.values()))
        weight = c4.slider("추천 가중치", 0, 100, 50, 5, help="높을수록 AI 추천 조합에 우선 반영돼요 (기본 50)")
        on_sale = c5.checkbox("판매 중", value=True)
        set_ok = c6.checkbox("세트 가능", value=True)
        if st.form_submit_button("메뉴 등록", type="primary"):
            try:
                repo.add_menu(category["id"], name, price, desc, image, not on_sale, spicy, weight, set_ok)
            except CategoryError as e:
                st.error(str(e))
            else:
                ss["menu_editor_v"] += 1
                st.toast(f"'{name.strip()}' 메뉴를 등록했어요.", icon="✅")
                st.rerun()


def render_menu_panel(repo, cats):
    """오른쪽: 선택한 카테고리의 메뉴 등록 + 등록된 메뉴 편집."""
    category = next((c for c in cats if c["id"] == ss["menu_cat"]), None)
    if category is None:
        st.info("👈 왼쪽에서 카테고리를 클릭하면 그 카테고리에 메뉴를 등록하고 수정할 수 있어요.")
        if cats:
            st.html(panel("카테고리별 메뉴 수", "카테고리를 선택하면 메뉴를 관리할 수 있어요",
                          bars({f"{c['icon']} {c['name']}": c["menu_count"] for c in cats}, "개")))
        return
    st.html(f'<div class="mmenu-head"><b>{category["icon"]} {category["name"]}</b><span>메뉴 {category["menu_count"]}개</span></div>')
    # 등록 양식과 메뉴 표를 탭으로 나눠 한 화면에 들어오게 한다.
    t_list, t_add = st.tabs(["등록된 메뉴", f"＋ '{category['name']}'에 메뉴 등록"])
    with t_add:
        render_menu_register_form(repo, category)
    with t_list:
        render_menu_editor(repo, category)


def render_menu_editor(repo, category):
    df = repo.menus()
    old = df[df["카테고리"] == category["name"]].reset_index(drop=True)
    if old.empty:
        st.caption("아직 등록된 메뉴가 없어요. ‘메뉴 등록’ 탭에서 첫 메뉴를 등록해 보세요.")
        return
    with st.container(key="menu_table"):  # 표 높이는 화면 높이에 맞춰 CSS 가 정한다
        edited = _menu_editor(old, category)
    save_menu_changes(repo, category, old, edited)


def _menu_editor(old, category):
    return st.data_editor(
        old, hide_index=True, width="stretch", num_rows="dynamic", disabled=["id"], height="stretch",
        key=f"menu_editor_{category['id']}_{ss['menu_editor_v']}",
        column_config={
            "id": None, "카테고리": None,
            "메뉴명": st.column_config.TextColumn(required=True),
            "가격": st.column_config.NumberColumn(min_value=0, step=500, format="%d원", required=True),
            "매운 정도": st.column_config.SelectboxColumn(options=list(SPICY_LABELS.values()), required=True),
            "추천 가중치": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, required=True),
            "이미지 URL": st.column_config.LinkColumn(),
            "판매 여부": st.column_config.CheckboxColumn(),
            "세트 가능": st.column_config.CheckboxColumn(),
        })


def save_menu_changes(repo, category, old, edited):
    st.caption("표에서 직접 고치거나 행을 추가·삭제한 뒤 저장하세요.")
    new = edited.reset_index(drop=True)
    dirty = not new.equals(old)
    c_save, c_undo, _ = st.columns([1, 1.3, 5])
    undo = c_undo.button("↩ 되돌리기", key="menu_undo", width="stretch", disabled=not dirty,
                         help="저장하기 전의 수정·추가·삭제를 모두 취소하고 저장된 상태로 돌립니다")
    if undo:
        ss["menu_editor_v"] += 1  # 편집 표를 새로 만들어 저장된 값으로 되돌린다
        st.toast("저장하지 않은 변경을 되돌렸어요.", icon="↩️")
        st.rerun()
    if c_save.button("변경 저장", type="primary", key="menu_save", width="stretch"):
        new["카테고리"] = category["name"]  # 표에서 새로 추가한 행도 이 카테고리에 들어간다
        try:
            r = repo.save_menus(new, old)
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["menu_editor_v"] += 1
            st.toast(f"저장했습니다. (수정 {r['saved']}개, 삭제 {r['deleted']}개)", icon="✅")
            st.rerun()


def page_menu(repo):
    page_head("메뉴 관리", "카테고리를 고른 뒤 메뉴를 등록하고 수정하세요")
    cats = repo.category_list()
    if ss["menu_cat"] and ss["menu_cat"] not in {c["id"] for c in cats}:
        ss["menu_cat"] = None  # 지워졌거나 서버에서 사라진 카테고리
    left, right = st.columns([1.15, 3.6], gap="large")
    with left:
        render_category_panel(repo, cats)
    with right:
        render_menu_panel(repo, cats)
