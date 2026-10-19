"""룰렛 상태 (남은 기회 계산, 돌리기).
"""

import random

import streamlit as st

import server

from user.state import context as ctx
from user.state.coupons import add_coupon


def spins_left():
    """남은 룰렛 기회 = 로그인했지만 아직 돌리지 않은 회원 수 (회원당 1회)."""
    return sum(1 for m in st.session_state.members if m["eligible"] and m["prize"] is None)


def pick_prize_index(prizes):
    """칸별 weight(관리자 '이벤트'에서 설정, 없으면 1)에 비례해 당첨 칸을 고른다. 합이 0 이면 모두 같은 확률."""
    weights = [max(float(p.get("weight", 1)), 0) for p in prizes]
    if not sum(weights):
        return random.randrange(len(prizes))
    return random.choices(range(len(prizes)), weights=weights)[0]


def slice_angles(prizes):
    """칸마다 (시작각, 각도)를 돌려준다. 각도 = 당첨 확률(weight 비율) x 360도. 12시 방향이 0도이고 시계 방향이다.
    weight 가 모두 0 이거나 없으면 모든 칸을 같은 크기로 나눈다."""
    weights = [max(float(p.get("weight", 1)), 0) for p in prizes]
    total = sum(weights)
    widths = [360 * w / total for w in weights] if total else [360 / len(prizes)] * len(prizes)
    starts = [sum(widths[:i]) for i in range(len(widths))]  # 앞 칸들의 각도를 더하면 이 칸의 시작각
    return list(zip(starts, widths))


def spin_roulette():
    ss = st.session_state
    row = next((m for m in ss.members if m["eligible"] and m["prize"] is None), None)
    if row is None:
        return
    server_result = server.play_roulette(ss.access_token, ss.table, row["id"]) if ss.access_token else None
    if server_result and server_result.get("error"):
        st.toast(server_result["error"], icon="⚠️")
        return
    # 서버 연결이 되면 서버가 고른 결과를 사용하고, 연결이 안 될 때만 기존 로컬 추첨을 쓴다.
    idx = server_result["index"] if server_result else pick_prize_index(ctx.ROULETTE_PRIZES)
    prize = server_result["prize"] if server_result else ctx.ROULETTE_PRIZES[idx]
    if server_result and idx >= len(ctx.ROULETTE_PRIZES):
        # 관리자 설정이 갱신되는 순간에도 화면의 회전 인덱스가 범위를 넘지 않게 맞춘다.
        idx = next((i for i, item in enumerate(ctx.ROULETTE_PRIZES) if item["short"] == prize["short"]), 0)
    start, width = slice_angles(ctx.ROULETTE_PRIZES)[idx]
    # 포인터(12시 방향) 아래에 당첨 칸의 실제 각도 범위(중앙 기준 +-30%) 안의 한 지점이 오도록 회전
    angle = 360 * 5 - (start + width / 2 + random.uniform(-width * 0.3, width * 0.3))
    ss.roulette = {"idx": idx, "angle": round(angle, 1), "animate": True}
    row["prize"] = prize["short"]
    coupon = server_result["coupon"] if server_result else None
    if ss.access_token and not server_result:  # 오프라인 대체 경로에서는 기존 저장 시도를 유지한다
        coupon = server.save_prize(ss.access_token, ss.table, row["id"], prize)
    add_coupon(row["id"], row["nickname"], prize, coupon)  # 당첨 결과는 쿠폰함으로. 쓸 때 장바구니에 적용한다
    ss.just_spun = True
