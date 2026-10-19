"""마케팅 화면 (AI 챗봇 · AI 추천 · AI 문자).
"""

from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

import admin_repository as repo_mod
import marketing_ai
from admin.marketing.config import RECOMMENDATION_PAGE_SIZE
from admin.marketing.recommendations import pick_recommendations as pick_recommendation_page
from admin.marketing.recommendations import regular_preference_cards, regular_preference_preview_cards, table_suggestions
from admin.marketing.table_map import table_map_svg
from admin.ui.widgets import kpi, page_head, sec_title
from admin.views.growth_performance import page_growth_performance
from admin_dummy_data import Unsupported
from admin_repository import GRADES

ss = st.session_state


STATUS_LABEL = {"sent": ("발송됨", "ok"), "dry_run": ("테스트(DRY RUN)", "warn"), "failed": ("실패", "bad"),
                "scheduled": ("예약됨", "ok"), "canceled": ("취소됨", "warn")}


def recipient_editor(pool, grades):
    """대상 등급의 수신 가능 회원 목록. 체크를 풀면 그 회원은 발송에서 제외된다. 선택된 회원 id 를 돌려준다."""
    rows = pool[pool["등급"].isin(grades)][["customer_id", "닉네임", "등급", "방문 횟수", "마지막 방문일"]].copy()
    excluded = ss.setdefault("sms_excluded", set())
    selected = ~rows["customer_id"].isin(excluded)
    # 추천 실행 이후 새로 가입한 회원까지 자동으로 선택되지 않게 추천 대상 ID를 유지한다.
    targets = ss.get("sms_recommendation_member_ids")
    if targets is not None:
        selected &= rows["customer_id"].isin(targets)
    rows.insert(0, "발송", selected)
    edited = st.data_editor(rows, hide_index=True, width="stretch", height=min(320, 36 + 35 * len(rows)),
                            disabled=[c for c in rows.columns if c != "발송"],
                            column_config={"customer_id": None},
                            key=f"sms_editor_{ss.get('sms_editor_v', 0)}_{'_'.join(grades)}")
    ss["sms_excluded"] = (excluded - set(rows["customer_id"])) | set(edited.loc[~edited["발송"], "customer_id"])
    if targets is not None:
        # 사장님이 목록에서 직접 체크한 변경은 유지하고, 표시하지 않은 등급의 선택은 보존한다.
        ss["sms_recommendation_member_ids"] = (targets - set(rows["customer_id"])) | set(edited.loc[edited["발송"], "customer_id"])
    return [int(i) for i in edited.loc[edited["발송"], "customer_id"]]


def usage_card(label, used):
    """이번 달 발송 건수만 보여 주는 카드 (한도·사용률은 표시하지 않는다)."""
    return (f'<div class="kpi"><div class="k">{escape(label)}</div>'
            f'<div class="v">{used}<small>건</small></div></div>')


def phone_preview(plan, body_empty):
    if body_empty or not plan:
        bubble = '<div class="bubble empty">본문을 입력하면 실제 발송 문구가 여기에 보여요</div>'
        meta = ""
    else:
        bubble = f'<div class="bubble">{escape(plan["content"]).replace(chr(10), "<br>")}</div>'
        pct = min(100, plan["bytes"] / 90 * 100) if plan["type"] == "SMS" else 100
        meta = (f'<div class="pmeta"><span class="pill">{plan["type"]}</span><span>{plan["bytes"]}바이트</span>'
                f'<span class="pbar"><i style="width:{pct:.0f}%"></i></span></div>')
    return (f'<div class="phone"><div class="notch"></div><div class="pscreen"><div class="pfrom">{"역전할머니맥주"}'
            f'<small>광고 문자</small></div>{bubble}</div></div>{meta}')


def kst_text(ts):
    """서버가 주는 UTC 시각 문자열을 한국 시간 'YYYY-MM-DD HH:MM' 으로."""
    try:
        t = datetime.fromisoformat(str(ts))
        t = t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
        return t.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(ts)[:16]


def sms_history(logs):
    if not logs:
        return '<div class="empty">아직 발송 내역이 없어요.</div>'
    rows = ""
    for log in logs:
        label, tone = STATUS_LABEL.get(log["status"], (log["status"], "warn"))
        text = escape(log["content"].split("\n")[1] if "\n" in log["content"] else log["content"])
        err = f'<div class="herr">{escape(log["error"])}</div>' if log.get("error") else ""
        if log.get("scheduled_at"):
            err += f'<div class="hsub">예약 {kst_text(log["scheduled_at"])}</div>'
        rows += (f'<div class="hrow"><div class="ht">{kst_text(log["ts"])}</div>'
                 f'<div class="hb"><div class="hmsg">{text}</div>{err}</div>'
                 f'<span class="tag {tone}">{label}</span><span class="pill">{log["type"]}</span>'
                 f'<div class="hn">{log["target_count"]}명</div></div>')
    return f'<div class="history">{rows}</div>'


def marketing_dashboard(repo):
    try:
        usage = repo.sms_usage()
    except Unsupported as e:
        st.info(f"{e} 서버를 켜고 `DATA_SOURCE=api` (또는 auto)로 실행하세요.")
        return
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
        st.error(f"서버에서 정보를 가져오지 못했습니다: {e}")
        return
    members = repo.members(ss["grade_rule"])
    if ss.get("sms_recommendation_notice"):
        st.success(ss["sms_recommendation_notice"])
    # 서버의 실제 문자 대상 기준과 동일하게 전화번호가 있는 동의 회원만 센다.
    pool = members[members["전화번호 보유"] & members["마케팅 수신 동의"] & ~members["수신거부"]]
    # 솔라피 충전 잔액: 조회가 안 되면(키 없음·오류) 이유를 카드에 보여 준다. 더미 모드에는 없으므로 건너뛴다.
    try:
        bal = repo.sms_balance()
    except (Unsupported, AttributeError, repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        bal = {"available": False, "reason": "서버에 연결되지 않았습니다."}
    st.html('<div class="kpis">'
            + usage_card("이번 달 SMS", usage["used"]["SMS"])
            + usage_card("이번 달 LMS", usage["used"]["LMS"])
            + (kpi("솔라피 잔액", f'{int(bal["balance"]):,}', "원", sub=f'포인트 {int(bal["point"]):,}원')
               if bal.get("available") else kpi("솔라피 잔액", "-", "", sub=bal.get("reason", "조회할 수 없습니다.")))
            + kpi("발송 가능 고객", len(pool), "명", sub=f"전체 회원 {len(members)}명 중 전화번호·수신 동의 확인", accent=True)
            + kpi("수신거부", int(members["수신거부"].sum()), "명", sub="발송 대상에서 자동 제외") + "</div>")
    # 한 화면에 들어오도록 작성 / 발송 내역 / 수신거부·안내를 탭으로 나눈다.
    t_write, t_history, t_optout = st.tabs(["문자 작성", "발송 내역", "수신거부 · 안내"])
    with t_write:
        left, right = st.columns([3, 2], gap="large")
        compose = left.container(key="sms_compose")
    with compose:
        ss.setdefault("sms_grades", ["휴면"])
        ss.setdefault("sms_body", "오랜만이에요! 이번 주 방문하시면 안주 10% 할인해 드려요.")
        by_grade = pool["등급"].value_counts()
        grades = st.multiselect("대상 등급", GRADES, key="sms_grades",
                                format_func=lambda g: f"{g} ({int(by_grade.get(g, 0))}명)")
        member_ids = None
        if grades:
            with st.expander(f"수신자 목록 ({int(sum(by_grade.get(g, 0) for g in grades))}명) — 체크를 풀면 제외돼요"):
                member_ids = recipient_editor(pool, grades)
                st.caption(f"선택 {len(member_ids)}명. 다른 등급을 더하려면 위 ‘대상 등급’에서 추가하세요.")
        body = st.text_area("본문", key="sms_body", height=100, help="앞에 (광고) 표기와 뒤에 수신거부 안내가 자동으로 붙어요")
        scheduled_at = None
        if st.checkbox("예약 발송", key="sms_schedule", help="지금부터 10분 이후, 야간(21~08시) 제외"):
            d_col, t_col = st.columns(2)
            soon = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None) + timedelta(hours=1)
            day = d_col.date_input("예약 날짜", value=soon.date(), min_value=soon.date(), key="sms_day")
            hhmm = t_col.time_input("예약 시각", value=soon.replace(minute=0, second=0, microsecond=0).time(), key="sms_time")
            scheduled_at = datetime.combine(day, hhmm)  # 시간대 없음 = KST
        plan = None
        if grades:
            try:
                plan = repo.sms_preview(grades, body, scheduled_at, member_ids)
            except repo_mod.api.ApiError as e:
                st.error(f"미리보기에 실패했습니다: {e.detail}")
        if plan:
            st.caption(f"{plan['bytes']}바이트 → **{plan['type']}** · 발송 대상 {plan['targets']}명 · 잔여 {plan['remaining']}건"
                       + (" · 🧪 DRY RUN (실제 전송 없음)" if plan["dry_run"] else ""))
            for problem in plan["problems"]:
                st.warning(problem)
        if st.button("예약" if scheduled_at else "발송", type="primary", disabled=not (plan and plan["ok"]), width="stretch"):
            try:
                r = repo.sms_send(grades, body, scheduled_at, member_ids)
                st.toast(f"{r['count']}명 " + ("예약했습니다." if scheduled_at else "발송 처리했습니다.")
                         + (" (DRY RUN)" if r["dry_run"] else ""), icon="✅")
            except repo_mod.api.ApiError as e:
                problems = e.detail.get("problems", []) if isinstance(e.detail, dict) else [str(e.detail)]
                st.error("발송하지 못했습니다: " + " / ".join(problems))
            else:
                st.rerun()
    with right:
        st.html(phone_preview(plan, not body.strip()))

    with t_optout:
        if repo.source == "dummy":
            st.caption("🧪 더미 데이터로 만든 화면이에요. 실제 문자는 전송되지 않고, 이 화면을 닫으면 발송 기록이 사라져요.")
        st.caption("수신 동의·휴대폰 번호가 있는 회원에게만, 야간(21~08시) 제외, 월 무료 한도 안에서 발송합니다. "
                   "서버 설정 `SMS_DRY_RUN=true` 이면 실제 문자는 전송되지 않고 기록만 남습니다.")
        sec_title("수신거부 처리")
        if not pool.empty:
            who = st.selectbox("회원", pool["customer_id"],
                               format_func=lambda i: f"#{i} {pool.set_index('customer_id').at[i, '닉네임']}")
            if st.button("수신거부로 등록"):
                repo.opt_out(int(who))
                st.rerun()
        else:
            st.caption("수신 동의한 회원이 없습니다.")
        st.caption(f"수신거부 회원 {int(members['수신거부'].sum())}명 — 발송 대상에서 제외됩니다.")

    logs = repo.sms_logs()
    with t_history:
        sec_title("발송 내역", f"{len(logs)}건")
        st.html(sms_history(logs))
        pending = [x for x in logs if x["status"] == "scheduled" and kst_text(x["scheduled_at"]) >= datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")]
        for log in pending:
            if st.button(f"예약 취소 · {kst_text(log['scheduled_at'])} · {log['target_count']}명", key=f"cancel_{log['id']}"):
                try:
                    repo.sms_cancel(log["id"])
                    st.toast("예약을 취소했습니다.", icon="✅")
                except (repo_mod.api.ApiError, Unsupported) as e:
                    st.error(f"취소하지 못했습니다: {getattr(e, 'detail', e)}")
                else:
                    st.rerun()


REC_PAGE_SIZE = RECOMMENDATION_PAGE_SIZE  # 기존 테스트·호출부에서 쓰는 이름은 유지한다.


def run_recommend(repo):
    """[AI 추천 받기]/[재추천] 버튼: 이때만 서버(제미나이)로 추천을 만든다. 화면에 들어오는 것만으로는 호출하지 않는다."""
    if "mk_rec_result" in ss:  # 처음 누른 뒤의 버튼(재추천)은 다음 묶음으로 넘어간다
        ss["mk_rec_round"] = ss.get("mk_rec_round", 0) + 1
    try:
        # 재추천은 캐시를 건너뛰고 제미나이가 문구를 새로 만들게 한다(refresh).
        ss["mk_rec_result"] = repo.opportunities(ss.get("mk_rec_round", 0), refresh="mk_rec_result" in ss)
        ss.pop("mk_rec_error", None)
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
        # 콜백에서 예외가 나면 화면이 멈추므로 오류를 기억해 두었다가 화면에서 알린다
        ss["mk_rec_error"] = str(e)


def execute_sms_recommendation(repo, recommendation):
    """추천 대상을 유지한 채 AI 문자 화면으로 이동하고 문자 초안을 채운다."""
    members = repo.members(ss["grade_rule"])
    eligible = members[members["전화번호 보유"] & members["마케팅 수신 동의"] & ~members["수신거부"]]
    target_ids = set(recommendation.get("member_ids") or [])
    ss["sms_recommendation_member_ids"] = target_ids
    ss["sms_grades"] = recommendation.get("target_grades") or GRADES
    ss["sms_body"] = recommendation.get("sms_body") or recommendation["action"]
    # 같은 등급 전체가 아니라 분석된 세그먼트만 기본 체크되도록 나머지 회원을 제외한다.
    ss["sms_excluded"] = set(eligible["customer_id"]) - target_ids if target_ids else set()
    ss["sms_editor_v"] = ss.get("sms_editor_v", 0) + 1
    ss["ai_candidates"], ss["ai_picked"] = None, None
    ss["sms_recommendation_notice"] = f"‘{recommendation['title']}’ 추천의 대상과 AI 문자 초안을 불러왔어요."
    for key in ("nav_top", "nav_sub_대시보드", "nav_sub_고객 등급", "nav_sub_주문 이력"):
        ss[key] = None
    ss["nav_sub_마케팅"] = "AI 문자"
    st.query_params["page"], st.query_params["tab"] = "마케팅", "AI 문자"


def pick_recommendations(recs, round_no):
    """추천 목록에서 round_no 번째 묶음을 고른다. 끝까지 보면 처음으로 돌아간다. → (고른 목록, 묶음 번호, 전체 묶음 수)"""
    return pick_recommendation_page(recs, round_no)


TABLE_MAP_COLUMNS = 6  # 배치도 한 줄에 놓을 테이블 수


def _pick_table(number):
    """배치도에서 눌린 테이블을 기억해 옆 패널에 그 테이블의 제안을 보여 준다."""
    ss["mk_table_sel"] = number


def _render_table_map(repo, preferences):
    """매장 테이블 배치도(SVG). 제안이 있는 테이블만 강조하고, 선택한 테이블의 제안을 옆에 보여 준다."""
    try:
        total = int(repo.store()["tables"])
    except (KeyError, TypeError, ValueError, repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        total = 30  # 매장 정보를 못 읽어도 배치도는 보이도록 기본 테이블 수를 쓴다
    suggestions = table_suggestions(preferences)
    selected = ss.get("mk_table_sel")
    if selected not in suggestions:
        selected = next(iter(sorted(suggestions)), None)  # 처음에는 제안이 있는 첫 테이블을 보여 준다
    left, right = st.columns([3, 2], gap="large")
    with left.container(key="mk_table_map"):
        # st.html/markdown 은 보안상 <svg> 를 제거해 그림이 안 보이므로, SVG 를 이미지로 표시한다.
        st.image(table_map_svg(total, set(suggestions), selected), width="stretch")
        # SVG 는 눌러도 반응하지 않으므로, 제안이 있는 테이블만 버튼으로 골라 보게 한다
        if suggestions:
            st.caption("💡 제안이 있는 테이블을 눌러 내용을 확인하세요.")
            cols = st.columns(min(len(suggestions), TABLE_MAP_COLUMNS))
            for index, number in enumerate(sorted(suggestions)):
                cols[index % len(cols)].button(f"💡 {number}번", key=f"mk_table_{number}", width="stretch",
                                              type="primary" if number == selected else "secondary",
                                              on_click=_pick_table, args=(number,), help="응대 제안 보기")
    with right:
        if selected is None:
            st.info("오늘은 응대 제안이 있는 테이블이 없어요.")
            return
        tip = suggestions[selected]
        st.html('<div class="rec"><div class="rt">' + escape(f"{selected}번 테이블 · {tip['nickname']}님") + '</div>'
                f'<div class="rw">{escape(tip["context"])}<br>{escape("추천 이유: " + tip["reason"])}</div>'
                f'<div class="ra">{escape("추천 행동: " + tip["action"])}<br>'
                f'{escape("“" + tip["note"] + "”")}</div></div>')


def _render_regular_preferences(repo):
    """오늘 주문한 단골·주간 반복 방문·특별일 고객의 응대 제안을 표시한다. 배치도는 데이터가 없어도 항상 보인다."""
    try:
        preferences = repo.regular_preferences()
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        preferences = None  # 조회 실패: 아래에서 안내만 하고 배치도는 그대로 보여 준다
    cards = regular_preference_cards(preferences or [])
    if preferences is None:
        sec_title("손님 응대 제안")
        st.info("단골 손님 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.")
        _render_table_map(repo, [])
        return
    if not cards:
        # 실제 DB에 대상이 없을 때 예시 손님을 섞으면 고객 정보로 오해할 수 있다.
        if repo.source == "api":
            sec_title("손님 응대 제안")
            st.info("오늘 주문이 확인된 재방문 고객이 아직 없습니다. 새 주문 후 다시 확인해 주세요.")
            _render_table_map(repo, [])
            return
        # DB에 예시 회원을 넣지 않고도 발표에서 추천 동작과 문구를 보여줄 수 있게 한다.
        cards = regular_preference_preview_cards()
        sec_title("손님 응대 제안", "AI가 추천할 현장 응대를 미리 확인해 보세요")
        st.caption("지금은 추천 예정 예시예요. 단골 등급, 최근 7일 2일 이상 방문, 생일 또는 "
               "첫 방문 기념일이 확인된 손님이 오늘 주문하면 상황에 맞는 응대를 제안해요.")
        _render_table_map(repo, [])
    else:
        sec_title("손님 응대 제안", "단골과 특별한 방문 상황이 확인된 손님에게 응대를 제안해요")
        _render_table_map(repo, preferences)
    # 한 안내 안에서 손님별 제안을 읽기 쉽도록 줄바꿈하며, DB 텍스트는 먼저 이스케이프한다.
    body = "".join(f'<div class="rec" style="grid-column:1 / -1"><div class="rt">{escape(card["title"])}</div>'
                   f'<div class="rw">{escape(card["why"])}</div>'
                   f'<div class="ra">{escape(card["action"]).replace(chr(10), "<br>")}</div></div>' for card in cards)
    st.html(f'<div class="recs regular-preferences">{body}</div>')


def marketing_recommend_tab(repo):
    sec_title("사장님을 위한 AI 마케팅 추천", "문자로 방문을 유도할 추천과 현장에서 활용할 추천을 나눠 제안해요")
    round_no = ss.get("mk_rec_round", 0)
    result = ss.get("mk_rec_result")
    if ss.get("mk_rec_error"):
        st.error(f"DB 기반 마케팅 추천을 불러오지 못했어요: {ss['mk_rec_error']}")
    if result is None:
        # 처음 들어왔을 때는 AI를 부르지 않고, 버튼을 누르도록 안내한다.
        st.info("아래 [✨ AI 추천 받기] 버튼을 누르면 AI가 매장 데이터를 분석해 문자 추천과 기타 추천을 만들어 드려요.")
        st.button("✨ AI 추천 받기", key="mk_rerecommend", type="primary", on_click=run_recommend, args=(repo,),
                  help="누를 때만 AI 추천을 만들어요")
        _render_regular_preferences(repo)
        return
    # 각 목록을 따로 순환하므로 문자 추천과 현장 운영 추천을 한 화면에서 모두 확인할 수 있다.
    for kind, title, description in (
        ("sms", "1. AI 문자 추천", "감사 혜택·재방문·휴면 복귀·생일처럼 방문 계기가 분명한 추천이에요"),
        ("guide", "2. 기타 AI 추천", "취향에 맞춘 방문 응대와 메뉴·재고·매장 운영에 활용하세요"),
    ):
        sec_title(title, description)
        group = result["groups"][kind]
        recs = group["items"]
        if not recs:
            st.info("현재 문자로 안내할 추천이 없어요. 데이터와 발송 가능한 고객이 쌓이면 제안해 드려요."
                    if kind == "sms" else "현재 현장 응대·운영에 활용할 추가 추천이 없어요.")
            continue
        # 실행 버튼은 해당 문자 추천 카드와 같은 열에 붙여 대상을 혼동하지 않게 한다.
        card_columns = st.columns(len(recs))
        for index, recommendation in enumerate(recs):
            with card_columns[index]:
                st.html(f'<div class="rec recommendation-card"><div class="rt">{index + 1}. {escape(recommendation["title"])}</div>'
                        f'<div class="rw">{escape(recommendation["why"])}</div>'
                        f'<div class="ra">👉 {escape(recommendation["action"])}</div></div>')
                if kind == "sms":
                    st.button("✉️ AI 문자로 실행", key=f"mk_execute_{round_no}_{index}", width="stretch",
                              on_click=execute_sms_recommendation, args=(repo, recommendation),
                              help=f"{index + 1}번 추천 실행: {recommendation['title']}")
        st.caption(f"추천 {group['page']}/{group['pages']} · 전체 {group['total']}개 · 한 번에 최대 네 가지를 보여드려요")
    st.button("🔄 재추천", key="mk_rerecommend", on_click=run_recommend, args=(repo,),
              help="두 카테고리의 다음 추천을 AI가 새로 만들어요")
    _render_regular_preferences(repo)


def _open_chat(session: dict) -> None:
    """서버가 준 대화방 한 개를 화면 상태에 올린다. 목록 선택 상자도 같은 대화로 맞춘다."""
    ss["mk_chat_sid"], ss["mk_chat"], ss["mk_chat_pick"] = session["id"], session["messages"], session["id"]


def _server_chat(repo) -> list[dict]:
    """서버 챗봇 대화를 불러온다. 브라우저를 새로고침해도 서버(DB)에 저장된 가장 최근 대화를 이어서 보여 준다."""
    if "mk_chat_sid" not in ss:
        sessions = repo.chat_sessions()
        _open_chat(repo.chat_get(sessions[0]["id"]) if sessions else repo.chat_create())
    return ss["mk_chat"]


def _new_chat(repo) -> None:
    """[새 대화] 버튼: 새 대화방을 만들어 바로 열고 목록에 추가한다. 지금 대화가 비어 있으면 새로 만들지 않는다."""
    if len(ss.get("mk_chat", [])) <= 1:  # 인사 메시지뿐이면 이미 새 대화다 (빈 대화방이 목록에 쌓이지 않게)
        st.toast("이미 새 대화예요. 질문을 입력해 보세요.", icon="🆕")
        return
    try:
        _open_chat(repo.chat_create())
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:  # 콜백에서 예외가 나면 화면이 멈추므로 토스트로 알린다
        st.toast(f"새 대화를 만들지 못했어요: {e}", icon="⚠️")


def _switch_chat(repo) -> None:
    """대화 목록에서 고른 이전 대화를 불러와 이어서 질문할 수 있게 한다."""
    try:
        _open_chat(repo.chat_get(ss["mk_chat_pick"]))
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
        st.toast(f"대화를 불러오지 못했어요: {e}", icon="⚠️")


def _chat_label(session: dict) -> str:
    """목록에 보일 이름: 제목 + 마지막 대화 시각(한국 시간)."""
    when = datetime.fromisoformat(session["updated_at"]).astimezone(timezone(timedelta(hours=9)))
    return f"{session['title']} · {when:%m/%d %H:%M}"


def marketing_chatbot_tab(repo):
    sec_title("AI 챗봇", "궁금한 점을 물어보세요")
    server = repo.source == "api"
    chat = None
    if server:
        try:
            chat = _server_chat(repo)
            sessions = repo.chat_sessions()
        except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
            # API 모드에서 더미 주문으로 답하면 DB 답변처럼 오해할 수 있으므로 오류만 명확히 알린다.
            st.error(f"DB 기반 AI 챗봇을 불러오지 못했어요: {e}")
            return
    if server:
        st.caption("대화는 서버에 저장돼요. 목록에서 이전 대화를 골라 이어서 질문할 수 있어요.")
        labels = {s["id"]: _chat_label(s) for s in sessions}
        if ss["mk_chat_sid"] not in labels:  # 방금 만든 대화가 목록 조회보다 늦게 반영돼도 목록에 보이게 한다
            labels = {ss["mk_chat_sid"]: "새 대화", **labels}
        c_list, c_new = st.columns([4, 1], vertical_alignment="bottom")
        c_list.selectbox("대화 목록", list(labels), format_func=labels.get, key="mk_chat_pick",
                         on_change=_switch_chat, args=(repo,))
        c_new.button("🆕 새 대화", key="mk_chat_new", on_click=_new_chat, args=(repo,), width="stretch")
    else:
        st.caption("🧪 서버에 연결되지 않아 규칙 기반 모의 응답이에요.")
        chat = ss.setdefault("mk_chat_mock", [{"role": "assistant", "content": marketing_ai.GREETING}])
    # chat_input 을 컨테이너 안에 두면 화면 맨 아래에 고정되지 않고 패널 안에 놓인다(탭 전환 때 스크롤이 튀지 않는다).
    with st.container(border=True, key="mk_chat_panel"):
        box = st.container(height=380, border=False)
        prompt = st.chat_input("예) 저번주 총 매출 알려줘", key="mk_chat_input")
        if prompt and server:
            try:
                with st.spinner("답변을 만드는 중이에요..."):
                    chat.extend(repo.chat_send(ss["mk_chat_sid"], prompt))
                st.rerun()  # 첫 질문이면 대화방 제목이 바뀌므로 목록을 다시 불러온다 (ss 에 답변은 이미 들어 있다)
            except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
                st.toast(f"답변을 받지 못했어요: {e}", icon="⚠️")
        elif prompt:
            ctx = marketing_ai.build_context(repo, ss["grade_rule"])
            chat.append({"role": "user", "content": prompt})
            chat.append({"role": "assistant", "content": marketing_ai.get_client().reply(prompt, ctx, chat[:-1])})
        for msg in chat:
            box.chat_message(msg["role"]).write(msg["content"])


def page_marketing(repo, tab="AI 챗봇"):
    """마케팅 기능은 사이드바 하위 메뉴에서 고른다 (admin/app.py 의 SUBPAGES)."""
    if tab == "F&B그로스 성과":
        page_growth_performance(repo)
        return
    page_head("마케팅", "수신 동의한 회원에게 문자를 보내 재방문을 이끌어요")
    {"AI 챗봇": marketing_chatbot_tab, "AI 추천": marketing_recommend_tab, "AI 문자": marketing_dashboard}[tab](repo)
