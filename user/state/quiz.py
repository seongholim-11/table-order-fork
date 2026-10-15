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


def quiz_answer(qid, value):
    q = st.session_state.quiz
    edited = qid in q["answers"]
    q["answers"][qid] = value
    if edited and len(q["answers"]) == len(ctx.QUESTIONS):
        q["step"] = len(ctx.QUESTIONS)  # 이미 끝낸 질문을 고쳤다면 바로 결과로
    else:
        q["step"] = min(q["step"] + 1, len(ctx.QUESTIONS))  # 선택하면 바로 다음 질문으로


def quiz_back():
    q = st.session_state.quiz
    q["step"] = max(q["step"] - 1, 0)


def quiz_goto(step):
    st.session_state.quiz["step"] = step


def quiz_restart():
    st.session_state.quiz = {"step": 0, "answers": {}}
