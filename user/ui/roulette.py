"""룰렛 화면.
"""

import streamlit as st

from user.state import context as ctx
from user.state.roulette import spin_roulette, spins_left
from user.ui.login import login_dialog


CONFETTI = [(18, 18, 38, 12, "#f1566f", -35), (3, 40, 14, 14, "#5b8def", 20), (84, 6, 34, 11, "#37b36b", 30),
            (90, 40, 16, 16, "#9b6bd6", 10), (5, 70, 30, 10, "#2f8de0", 35), (96, 66, 24, 9, "#ffc933", 20)]


def render_roulette():
    ss = st.session_state
    prizes, spun = ctx.ROULETTE_PRIZES, ss.roulette
    n = len(prizes)
    seg = 360 / n
    gap = 1.2
    stops = ",".join(f'{p["color"]} {i * seg}deg {(i + 1) * seg - gap}deg,#fff {(i + 1) * seg - gap}deg {(i + 1) * seg}deg'
                     for i, p in enumerate(prizes))
    labels = "".join(
        f'<div class="rw-label" style="transform:rotate({i * seg}deg)"><span style="transform:rotate(calc({-i * seg}deg - var(--to, 0deg)))">'
        f'{p["label"]}<em>{p["emoji"]}</em></span></div>' for i, p in enumerate(prizes))
    dots = "".join(f'<div class="rw-dot" style="transform:rotate({k * 360 / 16}deg)"><i></i></div>' for k in range(16))
    conf = "".join(f'<div class="rw-conf" style="left:{x}%;top:{y}%;width:{w}px;height:{h}px;background:{col};transform:rotate({r}deg)"></div>'
                   for x, y, w, h, col, r in CONFETTI)
    fs = round(4 * min(1, 5.5 / n), 2)  # 칸이 많을수록 글자를 줄여 START 버튼·옆 칸과 겹치지 않게 한다 (룰렛 너비 기준 cqw)
    cls = " spin" if spun and spun["animate"] else ""
    to = f'--to:{spun["angle"]}deg;' if spun else ""
    st.html('<div class="rw-title"><div class="fork">🍴</div>'
            '<div class="q">오늘, 어떤 메뉴가 좋을까요?</div>'
            '<h2><i class="l1"></i><i class="l2"></i>행운의 <span>룰렛</span>을 돌려보세요!<i class="r1"></i><i class="r2"></i></h2>'
            '<div class="s">맛있는 식사와 함께 작은 행운도 받아가세요!</div></div>')
    with st.container(key="rw_box"):
        st.html('<div class="rw-stage"><div class="rw-stand"></div><div class="rw-ring"></div>'
                f'{dots}<div class="rw-pin"></div>'
                f'<div class="rw-wheel{cls}" style="--rw-fs:{fs};{to}background:conic-gradient(from {-seg / 2}deg,{stops})">{labels}</div>'
                f'{conf}<div class="rw-star" style="left:-8%;top:10%">⭐</div><div class="rw-star" style="right:-9%;top:28%">⭐</div>'
                '<div class="rw-bubble l">오늘의<br>작은 행운!<br>어떤 선물이<br>기다리고 있을까요?</div>'
                '<div class="rw-bubble r">맛있는 식사와<br>특별한 혜택을<br>함께! <span class="heart">♥</span></div></div>')
        left = spins_left()
        with st.container(key="rw_start"):
            clicked = st.button("START", type="primary", key="roulette_btn", on_click=spin_roulette if left else None)
    hint = (f"🎟️ 룰렛 기회 {left}회 남았어요 — START를 눌러 보세요!" if left
            else "한 번 더 돌리려면 다른 회원이 로그인해 주세요." if st.session_state.members
            else "START를 누르면 로그인 후 룰렛을 돌릴 수 있어요.")
    st.html(f'<div class="rw-hint">{hint}</div>')
    just_spun = st.session_state.pop("just_spun", False)  # 이번 클릭이 룰렛을 돌린 것이면 팝업을 띄우지 않는다
    if clicked and not left and not just_spun:  # 기회가 없으면 (처음이든 이미 돌렸든) 로그인 팝업
        login_dialog("again" if st.session_state.members else "spin")
    if spun:
        prize = prizes[spun["idx"]]
        note = "쿠폰함에 담았어요 · 주문 화면의 🎟️ 쿠폰함에서 사용하세요"
        reveal = " reveal" if spun["animate"] else ""
        st.html(f'<div class="rw-result{reveal}"><div class="t">축하합니다! 오늘의 행운은</div>'
                f'<div class="p">{prize["emoji"]} {prize["short"]}</div><div class="n">{note}</div></div>')
        spun["animate"] = False
