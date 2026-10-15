"""QR 로그인 팝업과 회원 정보 입력·회원 기록.
"""

import time
from html import escape

import streamlit as st

import server
from user.state.login import ensure_login, new_login, poll_login_once


@st.cache_resource(show_spinner=False)
def qr_data_uri(url: str) -> str:
    """로그인 팝업에서 가운데 정렬로 보여줄 큰 QR (PNG data URI)."""
    import base64
    import io
    import qrcode
    buf = io.BytesIO()
    qrcode.make(url, box_size=8, border=2).convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


LOGIN_STEPS = ["QR 스캔", "카카오 로그인", "완료"]


def login_steps_html(active: int) -> str:
    """진행 단계 표시. active: 0 스캔 대기, 1 카카오 로그인 대기, -1 만료."""
    chips = ""
    for i, name in enumerate(LOGIN_STEPS):
        state = "active" if i == active else "done" if 0 <= active and i < active else ""
        chips += f'<div class="ls {state}"><i>{i + 1}</i><span>{name}</span></div>'
    return f'<div class="login-steps">{chips}</div>'


@st.fragment(run_every=2)
def login_watch():
    """로그인 팝업이 열려 있는 동안 2초마다 확인한다 (서버는 WebSocket 도 지원)."""
    ss = st.session_state
    login = ss.login
    if not login:
        return
    event = poll_login_once()
    if not ss.login:  # 로그인 완료 → 전체 화면을 다시 그려 팝업을 닫는다
        st.rerun()
    left = max(0, int(login["expires_in"] - (time.time() - login["created"])))
    status = "expired" if left == 0 else (event or {}).get("status", "waiting")
    dim = " expired" if status == "expired" else ""
    st.html(f'<div class="login-qr{dim}"><img src="{qr_data_uri(login["qr_url"])}" alt="로그인 QR 코드">'
            + ('<span class="login-qr-badge">만료됨</span>' if dim else "") + '</div>')
    if status == "expired":
        st.html(login_steps_html(-1) + '<div class="login-status expired">QR이 만료되었어요. 아래 버튼으로 새 QR을 받아 주세요.</div>')
    elif status == "scanned":
        st.html(login_steps_html(1) + '<div class="login-status scanned">📱 스캔 완료! 휴대폰에서 카카오 로그인을 마쳐 주세요</div>'
                f'<div class="login-timer">남은 시간 {left // 60}:{left % 60:02d}</div>')
    else:
        st.html(login_steps_html(0) + '<div class="login-status">휴대폰 카메라로 위 QR을 스캔해 주세요</div>'
                f'<div class="login-timer">남은 시간 {left // 60}:{left % 60:02d}</div>')
    # 재생성: 상태와 관계없이 항상 노출 (만료 시에는 주 버튼, 그 외에는 보조 버튼)
    st.button("🔄 QR 재생성", key="login_refresh", on_click=new_login, width="stretch",
              type="primary" if status == "expired" else "secondary")


LOGIN_REASON = {"spin": ("룰렛을 돌리려면 로그인해 주세요", "로그인하면 룰렛을 한 번 돌릴 수 있어요 (회원당 1회)"),
                "again": ("한 번 더 돌리려면 다른 회원이 로그인해 주세요", "이미 돌린 회원은 다시 돌릴 수 없어요 (회원당 1회)"),
                "more": ("다른 회원도 로그인할 수 있어요", "처음 로그인하는 회원은 룰렛을 한 번 돌릴 수 있어요")}


@st.dialog("📱 휴대폰으로 로그인", width="medium")
def login_dialog(reason="spin"):
    ss = st.session_state
    if server.is_online():
        ensure_login()  # 서버가 안 닿으면 여기서 오프라인으로 표시된다
    if not ss.login:
        st.html('<div class="login-pop"><div class="login-icon">🔌</div><b>로그인을 사용할 수 없어요</b>'
                '<small>' + ("서버에 연결할 수 없어요. 직원에게 문의해 주세요." if not server.is_online()
                             else "로그인 QR을 만들지 못했어요. 잠시 후 다시 시도해 주세요.") +
                '<br>로그인하지 않아도 주문은 가능해요.</small></div>')
        return
    title, sub = LOGIN_REASON[reason]
    st.html(f'<div class="login-pop"><b>{title}</b><small>{sub}</small></div>')
    login_watch()
    st.html('<div class="login-foot">로그인하지 않아도 주문은 할 수 있어요. 창을 닫아도 됩니다.</div>')


def render_profile_form():
    """카카오로 받지 못하는 정보(휴대폰 번호 등)와 마케팅 수신 동의를 직접 입력받는다. 모두 선택."""
    ss = st.session_state
    with st.expander(f"📱 {escape(ss.member['nickname'])}님 회원 정보 입력 (선택)", expanded=not ss.get("profile_saved")):
        with st.form("profile_form"):
            phone = st.text_input("휴대폰 번호", placeholder="010-1234-5678")
            c1, c2 = st.columns(2)
            year = c1.number_input("출생연도", 1920, 2020, value=None, step=1)
            gender = c2.selectbox("성별", ["선택 안 함", "남", "여"])
            consent = st.checkbox("(선택) 쿠폰·이벤트 등 광고성 문자 수신에 동의합니다.")
            st.caption("※ 임시 문구입니다. 정식 서비스 전에 개인정보 처리방침과 동의 문구를 확정해야 해요. "
                       "광고 문자는 21시~08시에는 보내지 않고, 문자 하단 안내로 언제든 수신을 거부할 수 있어요.")
            if st.form_submit_button("저장", type="primary"):
                ok, msg = server.update_profile(
                    ss.access_token, phone=phone.strip() or None, birth_year=int(year) if year else None,
                    gender={"남": "male", "여": "female"}.get(gender), marketing_consent=consent)
                ss.profile_saved = ok
                (st.success if ok else st.error)(msg)
        if st.button("문자 수신거부", key="opt_out_btn"):
            st.toast("수신거부 처리했어요." if server.opt_out(ss.access_token) else "처리하지 못했어요.", icon="🔕")


def render_members_log():
    """이 태블릿에서 로그인한 회원을 로그인할 때마다 아래에 누적해서 보여준다."""
    members = st.session_state.members
    if not members:
        return
    rows = ""
    for i, m in enumerate(members, 1):
        status = (f"🎁 {escape(m['prize'])}" if m["prize"] else "🎟️ 룰렛 대기 중" if m["eligible"]
                  else "룰렛은 이미 참여했어요")
        rows += (f'<li><span class="n">{i}</span><b>{escape(m["nickname"])}님</b>'
                 f'<span class="t">{m["at"]} 로그인</span><em>{status}</em></li>')
    st.html(f'<div class="mlog"><div class="mlog-title">로그인한 회원 <span>{len(members)}</span></div><ul>{rows}</ul></div>')
