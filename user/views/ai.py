"""AI 추천 조합 화면과 AI 질문 화면.
"""

from html import escape

import streamlit as st

from ai_quiz_data import answer_label, current_weather, time_slot
from menu_images import menu_image_html
from recommendations import recommend_combos
from user.state import context as ctx
from user.state.cart import add_combo
from user.state.quiz import quiz_answer, quiz_back, quiz_goto, quiz_restart, first_unanswered, reachable_steps
from user.state.session import go
from user.ui.common import won


def log_recommendation(params, combos):
    """추천 조합이 노출된 사실을 저장소에 남긴다(AI 추천 적중률 계산용). 같은 결과는 한 번만."""
    ss = st.session_state
    key = (tuple(sorted(params.items(), key=lambda kv: kv[0])), tuple(c["id"] for c in combos))
    if combos and ss.get("last_rec_key") != key:
        ss.last_rec_key = key
        # 돌려받은 추천 기록 id 를 세션에 기억해 두었다가, AI 조합을 담아 주문할 때 주문에 연결한다.
        event_id = ctx.REPO.log_recommendation(ss.table, params, [c["id"] for c in combos], ss.access_token)
        if event_id:
            ss.last_rec_event_id = event_id


def recommend_cached(scope, params, lines):
    """같은 화면(scope)·같은 답변이면 처음 계산한 추천을 세션에 저장해 그대로 돌려준다.

    조합을 담으면 화면이 다시 그려지는데, 그때마다 새로 계산하면 장바구니 내용이 바뀌어
    추천이 달라지고 제미나이 호출(토큰)도 반복된다. 그래서 화면에 들어왔을 때 한 번만 계산한다.
    캐시는 다른 카테고리로 나가거나 AI 질문을 시작/다시 시작할 때, '새로 추천받기'를 누를 때 지워진다.
    """
    ss = st.session_state
    key = (scope, tuple(sorted((k, str(v)) for k, v in params.items() if k != "hour")))
    cache = ss.get("rec_cache")
    if not cache or cache["key"] != key:
        combos, source = recommend_with_ai(params, lines)
        cache = ss.rec_cache = {"key": key, "combos": combos, "source": source}
    return cache["combos"], cache["source"]


def reset_recommendation_cache():
    st.session_state.pop("rec_cache", None)


def recommend_with_ai(params, lines):
    """API 모드에서는 DB 기반 제미나이 추천을 먼저 쓰고, 실패하면 기존 규칙 추천을 쓴다."""
    ss = st.session_state
    if getattr(ctx.REPO, "source", "dummy") == "api":
        result = ctx.REPO.generate_recommendations(ss.table, params, lines, ss.access_token)
        if result and result.get("combos"):
            return result["combos"], result.get("source", "gemini")
    return recommend_combos(
        params["people"], params["budget"], params["spicy"], params["drink"], lines,
        menu_by_id=ctx.MENU_BY_ID, rules=ctx.RULES, member=bool(ss.member),
        hour=params.get("hour"), weather=params.get("weather"), hunger=params.get("hunger", "적당해요"),
        stress=params.get("stress", "보통"), kind=params.get("kind", "any"),
        intent=params.get("intent"), gender=params.get("gender"),
    ), "rules"


def render_combo_cards(combos):
    """추천 조합 카드와 '담기' 버튼 (AI 추천 조합 화면과 AI 질문 결과가 함께 쓴다).
    조합 할인은 회원에게만 적용되므로 비회원 카드는 정가로 보이고 로그인 안내를 붙인다."""
    is_member = bool(st.session_state.member)
    for rank, combo in enumerate(combos, 1):
        with st.container(key=f"ai_combo_{rank}"):
            contents = "".join(
                f'<div class="combo-item">{menu_image_html(ctx.MENU_BY_ID.get(c["id"], c), "combo-photo", "combo-emoji")}'
                f'<span class="combo-name">{escape(c["name"])}<small>{escape(c["opt"])}</small></span><b>× {c["qty"]}</b></div>'
                for c in combo["components"])
            if is_member:
                pricing = (f'<div class="combo-price-main"><span class="combo-discount">회원 {ctx.DISCOUNT_PERCENT}% 할인</span>'
                           f'<del>{won(combo["original"])}</del><strong>{won(combo["price"])}</strong></div>'
                           f'<small>{won(combo["discount"])} 절약</small>')
            else:
                pricing = (f'<div class="combo-price-main"><strong>{won(combo["price"])}</strong></div>'
                           f'<small class="combo-member-note">🔒 회원 로그인 시 {ctx.DISCOUNT_PERCENT}% 할인</small>')
            st.html(f'<div class="combo-heading"><span class="combo-rank rank-{rank}">{rank}위</span>'
                    f'<h3>{escape(str(combo["name"]))}</h3>{"<span class=\"combo-top\">가장 추천해요</span>" if rank == 1 else ""}</div>'
                    f'<div class="combo-section-label">구성 메뉴</div>'
                    f'<div class="combo-items">{contents}</div>'
                    f'<div class="combo-reason"><strong>✨ 이 조합을 추천한 이유</strong><p>{escape(str(combo["reason"]))}</p></div>'
                    f'<div class="combo-pricing">{pricing}</div>')
            if st.button(f"{rank}위 조합 담기 · {won(combo['price'])}", key=f"add_combo_{rank}",
                         type="primary" if rank == 1 else "secondary", width="stretch"):
                add_combo(combo)
                st.toast("할인된 가격으로 조합을 담았어요" if is_member else "조합을 담았어요", icon="🛒")
                st.rerun()


DEFAULT_PREFERENCES = (2, 40000, "상관없어요", "맥주")  # 인원, 예산, 맵기, 음료


def render_recommendations():
    st.html('<div class="ai-hero"><div class="ai-eyebrow">✨ 오늘의 맞춤 메뉴</div>'
            '<h2>AI 추천 조합</h2><p>취향에 맞는 한 상, 조합 할인까지 한 번에.</p>'
            + (f'<span class="ai-offer">회원 혜택 · 조합 주문 시 {ctx.DISCOUNT_PERCENT}% 할인 적용 중</span></div>' if st.session_state.member
               else f'<span class="ai-offer">회원 전용 · QR 로그인하면 조합 {ctx.DISCOUNT_PERCENT}% 할인</span></div>'))
    people, budget, spicy, drink = DEFAULT_PREFERENCES  # 조건 선택 영역 없이 기본 조건으로 추천한다 (세부 조건은 AI 질문에서)
    lines = list(st.session_state.cart.values()) + [line for order in st.session_state.orders for line in order["lines"]]
    params = {"people": people, "budget": budget, "spicy": spicy, "drink": drink}
    combos, source = recommend_cached("ai", params, lines)
    log_recommendation({"people": people, "budget": budget, "spicy": spicy, "drink": drink}, combos)
    st.html(f'<div class="section-title ai-results-title">나에게 맞는 추천 <span>{len(combos)}</span>'
            f'<small>{people}명 · {won(budget)} 이하</small></div>')
    if not combos:
        st.info("지금 추천할 수 있는 조합이 없어요. AI 질문으로 조건을 바꿔 보세요.")
    render_combo_cards(combos)
    st.button("🔄 새로 추천받기", key="ai_refresh", on_click=reset_recommendation_cache, width="stretch")
    st.caption("DB의 메뉴·재고·추천 규칙을 제미나이가 분석한 추천입니다. 조합 할인은 회원에게만 적용됩니다."
               if source == "gemini" else
               "AI 서버를 사용할 수 없어 규칙 기반 추천을 표시하고 있습니다. 조합 할인은 회원에게만 적용됩니다.")


def render_quiz_question(step):
    q = ctx.QUESTIONS[step]
    answers = st.session_state.quiz["answers"]
    with st.container(key="quiz_top"):
        c_back, c_bar, c_close = st.columns([1.2, 5, 2.4], vertical_alignment="center")
    c_back.button("←", key="quiz_back", on_click=quiz_back, disabled=step == 0, width="stretch", help="이전 질문")
    with c_bar, st.container(horizontal=True, key="quiz_steps"):  # 질문 수만큼 나뉜 진행바: 답한 칸은 채워지고, 누르면 그 질문으로 이동
        for i, question in enumerate(ctx.QUESTIONS):
            st.button(f"{i + 1}", key=f"quiz_step_{i}", on_click=quiz_goto, args=(i,), disabled=i not in reachable_steps(),
                      type="primary" if i == step else "secondary", width="stretch",
                      help=f"{question['title']}" + (" (답변 완료 · 눌러서 수정)" if question["id"] in answers else ""))
    c_close.button("🍽️ 메뉴로 돌아가기", key="quiz_close", on_click=go, args=("menu",), width="stretch", help="질문을 그만하고 메뉴 화면으로 돌아가기")
    st.html(f'<div class="qz-group">{escape(q["group"])}</div><h2 class="qz-title">{escape(q["title"])}</h2>')
    with st.container(horizontal=True, key="quiz_grid"):
        for i, o in enumerate(q["options"]):
            with st.container(key=f"quiz_opt_{i}"):
                st.html(f'<div class="qz-emoji">{o["emoji"]}</div>')
                st.button(o["label"], key=f"quiz_pick_{q['id']}_{i}", width="stretch", on_click=quiz_answer,
                          args=(q["id"], o["value"]), type="primary" if answers.get(q["id"]) == o["value"] else "secondary")
    st.html('<div class="qz-hint">선택하면 바로 다음 질문으로 넘어가요 · 시간대와 날씨는 자동으로 반영돼요</div>')


def render_quiz_result():
    ss = st.session_state
    a = ss.quiz["answers"]
    hour, slot = time_slot()
    weather = current_weather(ctx.WEATHER, st.query_params.get("weather"))
    w_label, w_icon = ctx.WEATHER["types"][weather]["label"], ctx.WEATHER["types"][weather]["icon"]
    lines = list(ss.cart.values()) + [line for order in ss.orders for line in order["lines"]]
    params = {**a, "drink": "맥주", "hour": hour, "weather": weather}
    combos, source = recommend_cached("quiz", params, lines)
    log_recommendation(params, combos)
    st.html('<div class="ai-hero"><div class="ai-eyebrow">✨ AI 질문 결과</div><h2>맞춤 메뉴 조합이 완성됐어요</h2>'
            f'<p>답변해 주신 {len(ctx.QUESTIONS)}가지와 오늘의 상황을 반영했어요.</p></div>')
    with st.container(horizontal=True, key="quiz_answers"):
        for i, q in enumerate(ctx.QUESTIONS):
            st.button(answer_label(ctx.QUESTIONS, q["id"], a[q["id"]]), key=f"quiz_review_{q['id']}", on_click=quiz_goto, args=(i,),
                      help=f"{q['title']} 다시 고르기")
    st.caption("답변을 누르면 해당 질문으로 돌아가 수정할 수 있어요.")
    st.html(f'<div class="qz-auto">자동 반영 · 🕒 {slot} ({hour}시) · {w_icon} 날씨 {w_label} <small>(날씨는 더미 데이터)</small></div>')
    if not combos:
        st.info("선택한 조건에 맞는 조합이 없어요. 예산이나 인원을 바꿔서 다시 골라 보세요.")
        st.button("💵 예산 다시 고르기", key="quiz_edit_budget", on_click=quiz_goto, args=(len(ctx.QUESTIONS) - 1,))
    else:
        st.html(f'<div class="section-title ai-results-title">추천 조합 <span>{len(combos)}</span></div>')
        render_combo_cards(combos)
    c1, c2 = st.columns(2)
    c1.button("🔄 처음부터 다시 질문", key="quiz_restart", on_click=quiz_restart, width="stretch")
    c2.button("🍽️ 메뉴 보러가기", key="quiz_to_menu", on_click=go, args=("menu",), type="primary", width="stretch")
    st.caption("DB의 메뉴·재고·추천 규칙과 답변·오늘의 상황을 제미나이가 분석한 추천입니다. 조합 할인은 회원에게만 적용됩니다."
               if source == "gemini" else
               "AI 서버를 사용할 수 없어 규칙 기반 추천을 표시하고 있습니다. 조합 할인은 회원에게만 적용됩니다.")


def quiz_at_result():
    """결과 화면을 보여 줄 차례인가 (모든 질문에 답했고 마지막까지 넘어왔다)."""
    return st.session_state.quiz["step"] >= len(ctx.QUESTIONS) and first_unanswered() >= len(ctx.QUESTIONS)


def render_ai_quiz():
    quiz = st.session_state.quiz
    if quiz["step"] >= len(ctx.QUESTIONS) and first_unanswered() < len(ctx.QUESTIONS):
        quiz["step"] = first_unanswered()  # 답하지 않은 질문이 남았으면 결과 대신 그 질문으로
    step = quiz["step"]
    with st.container(key="quiz_page"):
        if step < len(ctx.QUESTIONS):
            render_quiz_question(step)
        else:
            render_quiz_result()
