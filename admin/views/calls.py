"""관리자 직원 호출 화면 — 처리 대기를 먼저 보여 주고 완료 처리를 제공한다."""

from datetime import datetime, timedelta, timezone

import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head, sec_title

KST = timezone(timedelta(hours=9))


def _time_text(iso: str) -> str:
    """서버의 ISO 시각을 매장에서 읽기 쉬운 한국 시각으로 바꾼다."""
    return datetime.fromisoformat(iso).astimezone(KST).strftime("오늘 %H:%M")


def _call_row(repo, call: dict, can_complete: bool) -> None:
    """한 호출의 테이블, 요청 품목, 요청 시각을 같은 형태로 표시한다."""
    with st.container(border=True):
        info, action = st.columns([5, 1.2], vertical_alignment="center")
        with info:
            st.markdown(f"#### {call['table_no']}번 테이블")
            st.write(" · ".join(call["items"]))
            st.caption(_time_text(call["ts"]))
        with action:
            if can_complete and st.button("처리 완료", key=f"call_done_{call['id']}",
                                          type="primary", use_container_width=True):
                repo.call_done(call["id"])
                st.toast(f"{call['table_no']}번 테이블 호출을 완료 처리했습니다.")
                st.rerun()
            if not can_complete:
                st.success("처리 완료")


def page_calls(repo) -> None:
    page_head("직원 호출", "테이블 요청을 확인하고 처리 완료로 변경할 수 있어요.")

    # 버튼을 누르면 Streamlit이 화면 전체를 다시 실행하므로 저장소의 최신 호출을 다시 읽는다.
    if st.button("새로고침", key="calls_refresh"):
        st.rerun()

    try:
        calls = repo.calls()
    except Exception as exc:  # API 연결 전에도 다른 관리자 화면은 계속 사용할 수 있게 안내한다.
        st.error(f"직원 호출을 불러오지 못했습니다: {exc}")
        return

    pending = sorted((call for call in calls if not call["done"]), key=lambda call: call["ts"], reverse=True)
    completed = sorted((call for call in calls if call["done"]), key=lambda call: call["ts"], reverse=True)
    kpi_row(
        kpi("처리 대기", len(pending), "건", "지금 확인이 필요한 호출", accent=True),
        kpi("처리 완료", len(completed), "건", "오늘 완료한 호출"),
        kpi("전체 호출", len(calls), "건", "오늘 접수 기준"),
    )

    sec_title("처리 대기", f"{len(pending)}건 · 최신순")
    if not pending:
        st.success("대기 중인 직원 호출이 없습니다.")
    for call in pending:
        _call_row(repo, call, can_complete=True)

    sec_title("처리 완료", f"{len(completed)}건 · 최신순")
    if not completed:
        st.info("아직 완료한 호출이 없습니다.")
    for call in completed:
        _call_row(repo, call, can_complete=False)
