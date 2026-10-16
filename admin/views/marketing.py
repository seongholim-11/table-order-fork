"""마케팅 화면 (AI 챗봇 · AI 추천 · AI 문자).
"""

from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

import admin_repository as repo_mod
import marketing_ai
from admin.marketing.config import RECOMMENDATION_PAGE_SIZE
from admin.marketing.recommendations import pick_recommendations as pick_recommendation_page
from admin.ui.widgets import kpi, page_head, sec_title
from admin_dummy_data import Unsupported
from admin_repository import GRADES

ss = st.session_state


STATUS_LABEL = {"sent": ("발송됨", "ok"), "dry_run": ("테스트(DRY RUN)", "warn"), "failed": ("실패", "bad"),
                "scheduled": ("예약됨", "ok"), "canceled": ("취소됨", "warn")}


def make_ai_candidates(repo):
    """[AI 문자 생성]: 수신자와 문구를 내부적으로 만들어 후보 버튼으로 보여 준다."""
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


def usage_card(label, used, limit):
    pct = min(100, used / limit * 100) if limit else 0
    tone = " hot" if pct >= 90 else ""
    return (f'<div class="kpi"><div class="k">{escape(label)}</div>'
            f'<div class="v">{used}<small>/ {limit}건</small></div>'
            f'<div class="meter{tone}"><i style="width:{pct:.0f}%"></i></div>'
            f'<div class="s">이번 달 무료 한도의 {pct:.0f}% 사용</div></div>')


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
    pool = members[members["마케팅 수신 동의"] & ~members["수신거부"]]
    st.html('<div class="kpis">'
            + usage_card("이번 달 SMS", usage["used"]["SMS"], usage["limit"]["SMS"])
            + usage_card("이번 달 LMS", usage["used"]["LMS"], usage["limit"]["LMS"])
            + kpi("발송 가능 고객", len(pool), "명", sub=f"전체 회원 {len(members)}명 중 수신 동의", accent=True)
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
        st.caption(f"수신거부 회원 {int(members['수신거부'].sum())}명 — 발송 대상에서 제외됩니다. (회원 본인은 태블릿에서도 거부할 수 있어요)")

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


def pick_recommendations(recs, round_no):
    """추천 목록에서 round_no 번째 묶음을 고른다. 끝까지 보면 처음으로 돌아간다. → (고른 목록, 묶음 번호, 전체 묶음 수)"""
    return pick_recommendation_page(recs, round_no)


def marketing_recommend_tab(repo):
    ctx = marketing_ai.build_context(repo, ss["grade_rule"])
    sec_title("사장님을 위한 마케팅 추천", "매장의 모든 데이터를 바탕으로 정리했어요")
    # 추천의 근거가 되는 핵심 숫자를 먼저 보여 줘서 사장님이 카드 내용을 빠르게 판단할 수 있게 한다.
    consumers, orders = ctx["members"], ctx["orders"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 고객", f"{consumers['total']:,}명")
    c2.metric("문자 발송 가능", f"{consumers['sendable']:,}명")
    c3.metric("누적 매출", f"{orders['revenue']:,}원")
    c4.metric("평균 주문금액", f"{orders['avg']:,}원")
    recs, page, pages = pick_recommendations(marketing_ai.recommend(ctx), ss.get("mk_rec_round", 0))
    cards = "".join(f'<div class="rec"><div class="rt">{i}. {escape(r["title"])}</div>'
                    f'<div class="rw">{escape(r["why"])}</div><div class="ra">👉 {escape(r["action"])}</div></div>'
                    for i, r in enumerate(recs, 1))
    st.html(f'<div class="recs">{cards}</div>')
    c_btn, c_note = st.columns([1, 4], vertical_alignment="center")
    c_btn.button("🔄 재추천", key="mk_rerecommend", on_click=next_rec_round, width="stretch",
                 help="다른 마케팅 방법을 추천받아요")
    c_note.caption(f"추천 {page}/{pages} · 눌러서 다른 마케팅 방법을 추천받아요" if pages > 1
                   else "지금은 추천할 방법이 이것뿐이에요. 데이터가 쌓이면 더 다양해져요.")


def marketing_chatbot_tab(repo):
    ctx = marketing_ai.build_context(repo, ss["grade_rule"])
    sec_title("AI 챗봇", "궁금한 점을 물어보세요")
    st.caption("🧪 지금은 규칙 기반 모의 응답이에요. 실제 AI(Claude API) 연동 지점은 `marketing_ai.py` 에 분리돼 있어요.")
    chat = ss.setdefault("mk_chat", [{"role": "assistant", "content": marketing_ai.GREETING}])
    # chat_input 을 컨테이너 안에 두면 화면 맨 아래에 고정되지 않고 패널 안에 놓인다(탭 전환 때 스크롤이 튀지 않는다).
    with st.container(border=True, key="mk_chat_panel"):
        box = st.container(height=380, border=False)
        prompt = st.chat_input("예) 휴면 고객을 어떻게 다시 오게 할까?", key="mk_chat_input")
        if prompt:
            chat.append({"role": "user", "content": prompt})
            chat.append({"role": "assistant", "content": marketing_ai.get_client().reply(prompt, ctx, chat[:-1])})
        for msg in chat:
            box.chat_message(msg["role"]).write(msg["content"])


def page_marketing(repo, tab="AI 챗봇"):
    """AI 챗봇 / AI 추천 / AI 문자 탭은 사이드바 하위 메뉴에서 고른다 (admin/app.py 의 SUBPAGES)."""
    page_head("마케팅", "수신 동의한 회원에게 문자를 보내 재방문을 이끌어요")
    {"AI 챗봇": marketing_chatbot_tab, "AI 추천": marketing_recommend_tab, "AI 문자": marketing_dashboard}[tab](repo)
