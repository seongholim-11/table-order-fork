"""룰렛 상태 (남은 기회 계산, 돌리기).
"""

import random

import streamlit as st

import server

from user.state import context as ctx
from user.state.cart import cart_add


def spins_left():
    """남은 룰렛 기회 = 로그인했지만 아직 돌리지 않은 회원 수 (회원당 1회)."""
    return sum(1 for m in st.session_state.members if m["eligible"] and m["prize"] is None)


def pick_prize_index(prizes):
    """칸별 weight(관리자 '이벤트'에서 설정, 없으면 1)에 비례해 당첨 칸을 고른다. 합이 0 이면 모두 같은 확률."""
    weights = [max(float(p.get("weight", 1)), 0) for p in prizes]
    if not sum(weights):
        return random.randrange(len(prizes))
    return random.choices(range(len(prizes)), weights=weights)[0]


def spin_roulette():
    ss = st.session_state
    row = next((m for m in ss.members if m["eligible"] and m["prize"] is None), None)
    if row is None:
        return
    idx = pick_prize_index(ctx.ROULETTE_PRIZES)
    seg = 360 / len(ctx.ROULETTE_PRIZES)
    # 포인터(12시 방향) 아래에 당첨 칸의 중앙 부근이 오도록 회전
    angle = 360 * 5 - (idx * seg + random.uniform(-seg * 0.3, seg * 0.3))
    ss.roulette = {"idx": idx, "angle": round(angle, 1), "animate": True}
    prize = ctx.ROULETTE_PRIZES[idx]
    row["prize"] = prize["short"]
    if ss.access_token:  # 새로고침해도 '이미 돌렸다'가 유지되도록 서버에 남긴다
        server.save_prize(ss.access_token, ss.table, row["id"], prize["short"])
    ss.just_spun = True
    if prize["kind"] == "discount":
        ss.roulette_percent = max(ss.roulette_percent, prize["percent"])
    elif prize["item_id"] in ctx.MENU_BY_ID:
        cart_add(ctx.MENU_BY_ID[prize["item_id"]], "룰렛 서비스", 0, 1)
