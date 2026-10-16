"""추천 가중치 화면 (메뉴 관리와 같은 구성: 왼쪽 카테고리 목록 + 오른쪽 표 편집).
"""

import streamlit as st

from admin.ui.widgets import page_head, sec_title

ss = st.session_state


def select_weight_category(category_id):
    ss["weights_cat"] = category_id


def render_category_panel(cats):
    """왼쪽: 카테고리 목록(클릭해서 선택)."""
    with st.container(border=True, key="mcat_panel"):
        st.html('<div class="mcat-title">📂 카테고리</div>')
        if not cats:
            st.html('<div class="mcat-hint">아직 카테고리가 없어요. 메뉴 관리에서 추가해 주세요.</div>')
        for c in cats:
            st.button(f"{c['icon']}  {c['name']}  ({c['menu_count']})", key=f"mcat_w_{c['id']}", width="stretch",
                      type="primary" if ss["weights_cat"] == c["id"] else "secondary",
                      on_click=select_weight_category, args=(c["id"],))


def render_weight_panel(repo, cats):
    """오른쪽: 선택한 카테고리 메뉴의 추천 가중치를 표에서 고치고 저장."""
    category = next((c for c in cats if c["id"] == ss["weights_cat"]), None)
    if category is None:
        st.info("👈 왼쪽에서 카테고리를 클릭하면 그 카테고리 메뉴의 추천 가중치를 수정할 수 있어요.")
        return
    st.html(f'<div class="mmenu-head"><b>{category["icon"]} {category["name"]}</b><span>메뉴 {category["menu_count"]}개</span></div>')

    sec_title("메뉴별 추천 가중치")
    menu = repo.menus()
    old = menu[menu["카테고리"] == category["name"]].reset_index(drop=True)
    if old.empty:
        st.caption("이 카테고리에는 아직 메뉴가 없어요. 메뉴 관리에서 먼저 등록해 주세요.")
        return
    with st.container(key="weights_table"):  # 표 높이는 화면 높이에 맞춰 CSS 가 정한다
        edited = st.data_editor(
            old, hide_index=True, width="stretch", num_rows="fixed", height="stretch",
            key=f"weights_editor_{category['id']}_{ss['weights_editor_v']}",
            disabled=[c for c in old.columns if c != "추천 가중치"],
            column_order=["메뉴명", "가격", "판매 여부", "추천 가중치"],
            column_config={
                "가격": st.column_config.NumberColumn(format="%d원"),
                "판매 여부": st.column_config.CheckboxColumn(),
                "추천 가중치": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, required=True,
                                                          help="0~100, 높을수록 AI 추천 조합에 우선 반영돼요 (기본 50)"),
            })
    st.caption("표의 '추천 가중치'를 직접 고친 뒤 저장하세요. 0~100, 높을수록 AI 추천 조합에 우선 반영돼요 (기본 50).")
    new = old.copy()
    new["추천 가중치"] = edited["추천 가중치"].reset_index(drop=True).fillna(50).astype(int).clip(0, 100)
    dirty = not new["추천 가중치"].equals(old["추천 가중치"].astype(int))
    c_save, c_undo, _ = st.columns([1, 1.3, 5])
    if c_undo.button("↩ 되돌리기", key="weights_undo", width="stretch", disabled=not dirty,
                     help="저장하기 전의 가중치 변경을 모두 취소하고 저장된 값으로 돌립니다"):
        ss["weights_editor_v"] += 1  # 편집 표를 새로 만들어 저장된 값으로 되돌린다
        st.toast("저장하지 않은 변경을 되돌렸어요.", icon="↩️")
        st.rerun()
    if c_save.button("변경 저장", type="primary", key="weights_save", width="stretch"):
        try:
            r = repo.save_menus(new, old)
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["weights_editor_v"] += 1
            st.toast(f"저장했습니다. (수정 {r['saved']}개)", icon="✅")
            st.rerun()


def page_weights(repo):
    page_head("추천 가중치", "카테고리를 고른 뒤 메뉴별 추천 가중치를 수정하세요")
    cats = repo.category_list()
    ss.setdefault("weights_editor_v", 0)
    ss.setdefault("weights_cat", None)
    if ss["weights_cat"] not in {c["id"] for c in cats}:
        ss["weights_cat"] = cats[0]["id"] if cats else None  # 처음엔 첫 카테고리를 보여준다
    left, right = st.columns([1.15, 3.6], gap="large")
    with left:
        render_category_panel(cats)
    with right:
        render_weight_panel(repo, cats)
