"""AI 질문 진행 상태.
"""

import streamlit as st

from user.state import context as ctx
from user.state.session import go


def open_quiz():
    st.session_state.quiz = {"step": 0, "answers": {}}
    go("ai_quiz")


def reachable_steps():
    """이동할 수 있는 질문 번호: 답변을 마친 질문 전부와 아직 답하지 않은 첫 질문."""
    answers = st.session_state.quiz["answers"]
    steps = []
    for i, q in enumerate(ctx.QUESTIONS):
        steps.append(i)
        if q["id"] not in answers:
            break
    return steps


def first_unanswered():
    """아직 답하지 않은 첫 질문 번호. 모두 답했으면 질문 수(=결과 화면)."""
    answers = st.session_state.quiz["answers"]
    return next((i for i, q in enumerate(ctx.QUESTIONS) if q["id"] not in answers), len(ctx.QUESTIONS))


def quiz_answer(qid, value):
    q = st.session_state.quiz
    edited = qid in q["answers"]
    q["answers"][qid] = value
    index = next(i for i, x in enumerate(ctx.QUESTIONS) if x["id"] == qid)
    if edited and first_unanswered() == len(ctx.QUESTIONS):
        q["step"] = len(ctx.QUESTIONS)  # 이미 끝낸 질문을 고쳤다면 바로 결과로
    else:
        # 눌린 질문 기준으로 다음 질문으로 (같은 버튼이 두 번 눌려도 건너뛰지 않는다)
        q["step"] = min(index + 1, len(ctx.QUESTIONS))


def quiz_back():
    q = st.session_state.quiz
    q["step"] = max(q["step"] - 1, 0)


def quiz_goto(step):
    st.session_state.quiz["step"] = step


def quiz_restart():
    st.session_state.quiz = {"step": 0, "answers": {}}
