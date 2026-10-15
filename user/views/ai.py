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
        ctx.REPO.log_recommendation(ss.table, params, [c["id"] for c in combos], ss.access_token)


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
                    f'<h3>{combo["name"]}</h3>{"<span class=\"combo-top\">가장 추천해요</span>" if rank == 1 else ""}</div>'
                    f'<div class="combo-section-label">구성 메뉴</div>'
                    f'<div class="combo-items">{contents}</div>'
                    f'<div class="combo-reason"><strong>✨ 이 조합을 추천한 이유</strong><p>{combo["reason"]}</p></div>'
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
    combos = recommend_combos(people, budget, spicy, drink, lines, menu_by_id=ctx.MENU_BY_ID, rules=ctx.RULES,
                              member=bool(st.session_state.member))
    log_recommendation({"people": people, "budget": budget, "spicy": spicy, "drink": drink}, combos)
    st.html(f'<div class="section-title ai-results-title">나에게 맞는 추천 <span>{len(combos)}</span>'
            f'<small>{people}명 · {won(budget)} 이하</small></div>')
    if not combos:
        st.info("지금 추천할 수 있는 조합이 없어요. AI 질문으로 조건을 바꿔 보세요.")
    render_combo_cards(combos)
    st.caption("현재는 취향과 주문 정보를 반영한 데모 추천입니다. 조합 할인은 회원에게만, 세트 단위로 적용됩니다.")


def render_quiz_question(step):
    q = ctx.QUESTIONS[step]
    answers = st.session_state.quiz["answers"]
    with st.container(key="quiz_top"):
        c_back, c_bar, c_close = st.columns([1.2, 5, 2.4], vertical_alignment="center")
    c_back.button("←", key="quiz_back", on_click=quiz_back, disabled=step == 0, width="stretch", help="이전 질문")
    c_bar.html(f'<div class="qz-progress"><span class="n">{step + 1}</span><div class="bar">'
               f'<i style="width:{(step + 1) / len(ctx.QUESTIONS) * 100:.0f}%"></i></div><span class="t">{len(ctx.QUESTIONS)}</span></div>')
    c_close.button("🍽️ 메뉴로 돌아가기", key="quiz_close", on_click=go, args=("menu",), width="stretch", help="질문을 그만하고 메뉴 화면으로 돌아가기")
    with st.container(horizontal=True, key="quiz_steps"):
        for i, question in enumerate(ctx.QUESTIONS):
            done = question["id"] in answers
            st.button(f"{i + 1}", key=f"quiz_step_{i}", on_click=quiz_goto, args=(i,), disabled=i not in reachable_steps(),
                      type="primary" if i == step else "secondary",
                      help=f"{question['title']}" + (" (답변 완료 · 눌러서 수정)" if done else ""))
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
    combos = recommend_combos(a["people"], a["budget"], a["spicy"], "맥주", lines, menu_by_id=ctx.MENU_BY_ID, rules=ctx.RULES,
                              hour=hour, weather=weather, hunger=a["hunger"], stress=a["stress"], kind=a["kind"],
                              intent=a["intent"], gender=a["gender"], member=bool(ss.member))
    log_recommendation({**a, "hour": hour, "weather": weather}, combos)
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
    st.caption("현재는 더미 데이터와 임시 규칙으로 만든 데모 추천입니다. 조합 할인은 회원에게만, 세트 단위로 적용됩니다.")


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
