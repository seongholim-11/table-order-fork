"""마케팅 화면 (AI 챗봇 · AI 추천 · AI 문자).
"""

from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

import admin_repository as repo_mod
import marketing_ai
from admin.marketing.config import RECOMMENDATION_PAGE_SIZE
from admin.marketing.recommendations import pick_recommendations as pick_recommendation_page
from admin.marketing.recommendations import regular_preference_cards, regular_preference_preview_cards
from admin.ui.widgets import kpi, page_head, sec_title
from admin.views.growth_performance import page_growth_performance
from admin_dummy_data import Unsupported
from admin_repository import GRADES

ss = st.session_state


STATUS_LABEL = {"sent": ("발송됨", "ok"), "dry_run": ("테스트(DRY RUN)", "warn"), "failed": ("실패", "bad"),
                "scheduled": ("예약됨", "ok"), "canceled": ("취소됨", "warn")}


def make_ai_candidates(repo):
    """[AI 문자 생성]: 수신자와 문구를 내부적으로 만들어 후보 버튼으로 보여 준다."""
    if repo.source == "api":
        # 서버가 매장 데이터·오늘 날씨/행사를 반영해 후보를 만든다 (AI 키가 없으면 템플릿)
        try:
            ss["ai_candidates"] = repo.sms_candidates()
        except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
            # 콜백에서 예외가 나면 화면이 'error' 로 멈추므로, 실패 이유를 알리고 후보만 비운다
            ss["ai_candidates"] = []
            st.toast(f"AI 문자 후보를 만들지 못했습니다: {e}", icon="⚠️")
    else:
        # 서버 없이 더미로 볼 때는 예전처럼 화면에서 직접 만든다
        ctx = marketing_ai.build_context(repo, ss["grade_rule"])
        ss["ai_candidates"] = marketing_ai.suggest_candidates(ctx, *marketing_ai.external_context())
    ss["ai_picked"] = None


def pick_ai_candidate(i):
    c = ss["ai_candidates"][i]
    ss["sms_grades"], ss["sms_body"], ss["ai_picked"] = c["grades"], c["body"], i
    ss["sms_excluded"] = set()  # 제외 체크는 새 후보를 고를 때마다 초기화
    ss["sms_editor_v"] = ss.get("sms_editor_v", 0) + 1


def candidate_label(c, pool_by_grade):
    n = sum(pool_by_grade.get(g, 0) for g in c["grades"])
    icons = "".join(marketing_ai.KEYWORD_ICON[k] for k in c["keywords"])
    return f"{icons} {' + '.join(c['keywords'])} · {n}명"


def recipient_editor(pool, grades):
    """대상 등급의 수신 가능 회원 목록. 체크를 풀면 그 회원은 발송에서 제외된다. 선택된 회원 id 를 돌려준다."""
    rows = pool[pool["등급"].isin(grades)][["customer_id", "닉네임", "등급", "방문 횟수", "마지막 방문일"]].copy()
    excluded = ss.setdefault("sms_excluded", set())
    rows.insert(0, "발송", ~rows["customer_id"].isin(excluded))
    edited = st.data_editor(rows, hide_index=True, width="stretch", height=min(320, 36 + 35 * len(rows)),
                            disabled=[c for c in rows.columns if c != "발송"],
                            column_config={"customer_id": None},
                            key=f"sms_editor_{ss.get('sms_editor_v', 0)}_{'_'.join(grades)}")
    ss["sms_excluded"] = (excluded - set(rows["customer_id"])) | set(edited.loc[~edited["발송"], "customer_id"])
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
        st.button("✨ AI 문자 생성", key="ai_sms_generate", type="secondary", width="stretch",
                  on_click=make_ai_candidates, args=(repo,),
                  help="수신 대상과 문구를 AI가 만들어 후보 버튼으로 보여줘요 (AI 키가 없으면 템플릿 문구)")
        cands = ss.get("ai_candidates")
        if cands:
            by_grade_pool = pool["등급"].value_counts().to_dict()
            st.html('<div class="tpl-label">추천 문자 — 고르면 아래에 수신자와 내용이 채워져요</div>')
            for i, c in enumerate(cands):
                st.button(candidate_label(c, by_grade_pool), key=f"ai_cand_{i}", width="stretch",
                          type="primary" if ss.get("ai_picked") == i else "secondary",
                          on_click=pick_ai_candidate, args=(i,))
            if ss.get("ai_picked") is not None and cands[ss["ai_picked"]]["source"] == "template":
                st.caption("AI 키가 없거나 호출에 실패해 템플릿 문구로 만들었어요.")
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


def next_rec_round():
    ss["mk_rec_round"] = ss.get("mk_rec_round", 0) + 1


def execute_sms_recommendation(repo, recommendation):
    """추천 대상을 유지한 채 AI 문자 화면으로 이동하고 문자 초안을 채운다."""
    members = repo.members(ss["grade_rule"])
    eligible = members[members["전화번호 보유"] & members["마케팅 수신 동의"] & ~members["수신거부"]]
    target_ids = set(recommendation.get("member_ids") or [])
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


def _render_regular_preferences(repo):
    """오늘 주문한 2회 이상 방문 고객의 실시간 응대 제안을 표시한다."""
    try:
        cards = regular_preference_cards(repo.regular_preferences())
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        # 추가 정보 조회가 실패해도 기존 추천 카드·재추천 버튼은 그대로 사용할 수 있다.
        st.info("단골 손님 정보를 불러오지 못했어요. 잠시 후 재추천을 눌러 주세요.")
        return
    if not cards:
        # 실제 DB에 대상이 없을 때 예시 손님을 섞으면 고객 정보로 오해할 수 있다.
        if repo.source == "api":
            sec_title("손님 응대 제안")
            st.info("오늘 주문이 확인된 재방문 고객이 아직 없습니다. 새 주문 후 재추천을 눌러 확인해 주세요.")
            return
        # DB에 예시 회원을 넣지 않고도 발표에서 추천 동작과 문구를 보여줄 수 있게 한다.
        cards = regular_preference_preview_cards(repo.customer_grade_rules()["repeat"])
        sec_title("손님 응대 제안", "AI가 추천할 현장 응대를 미리 확인해 보세요")
        st.caption("지금은 추천 예정 예시예요. 실제 2회 이상 방문 고객이 로그인하고 주문하면, "
                   "이전 방문·테이블·주문과 오늘 상황에 맞는 서비스 및 인사말로 바뀝니다. "
                   "새 주문과 상황에 따라 문구는 달라질 수 있어요.")
    else:
        sec_title("손님 응대 제안", "오늘 다시 온 손님을 알아보고 서비스할 때 참고해 주세요")
    # 한 안내 안에서 손님별 제안을 읽기 쉽도록 줄바꿈하며, DB 텍스트는 먼저 이스케이프한다.
    body = "".join(f'<div class="rec" style="grid-column:1 / -1"><div class="rt">{escape(card["title"])}</div>'
                   f'<div class="rw">{escape(card["why"])}</div>'
                   f'<div class="ra">{escape(card["action"]).replace(chr(10), "<br>")}</div></div>' for card in cards)
    st.html(f'<div class="recs regular-preferences">{body}</div>')


def marketing_recommend_tab(repo):
    sec_title("사장님을 위한 AI 마케팅 추천", "회원·방문·주문·메뉴 데이터를 조합해 네 가지씩 제안해요")
    round_no = ss.get("mk_rec_round", 0)
    try:
        # API는 실제 DB, 더미 모드는 1,000명 시연 자료를 같은 추천 계약으로 돌려준다.
        result = repo.opportunities(round_no)
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
        st.error(f"DB 기반 마케팅 추천을 불러오지 못했어요: {e}")
        return
    recs, page, pages = result["items"], result["page"], result["pages"]
    # 카드와 실행 버튼을 같은 열에서 바로 이어 그린다. 별도 버튼 행을 만들면 화면 폭에 따라
    # 버튼이 다른 번호의 카드 아래처럼 보일 수 있으므로, 각 버튼은 해당 추천 카드에 붙인다.
    card_columns = st.columns(len(recs))
    for index, recommendation in enumerate(recs):
        with card_columns[index]:
            st.html(f'<div class="rec recommendation-card"><div class="rt">{index + 1}. {escape(recommendation["title"])}</div>'
                    f'<div class="rw">{escape(recommendation["why"])}</div>'
                    f'<div class="ra">👉 {escape(recommendation["action"])}</div></div>')
            if recommendation.get("action_type") == "sms":
                st.button("✉️ AI 문자로 실행", key=f"mk_execute_{round_no}_{index}", width="stretch",
                          on_click=execute_sms_recommendation, args=(repo, recommendation),
                          help=f"{index + 1}번 추천 실행: {recommendation['title']}")
    c_btn, c_note = st.columns([1, 4], vertical_alignment="center")
    c_btn.button("🔄 재추천", key="mk_rerecommend", on_click=next_rec_round, width="stretch",
                 help="다른 마케팅 방법을 추천받아요")
    c_note.caption(f"추천 {page}/{pages} · 전체 {result.get('total', len(recs))}개 분석 중 다른 네 가지를 확인해요" if pages > 1
                   else "지금은 추천할 방법이 이것뿐이에요. 데이터가 쌓이면 더 다양해져요.")
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
