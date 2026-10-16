"""관리자 화면 공통 UI 조각 (제목·KPI 카드·막대 목록·패널).
"""

from html import escape

import streamlit as st


def page_head(title, sub=""):
    st.html(f'<div class="page-head"><div><h1>{escape(title)}</h1>'
            + (f"<p>{escape(sub)}</p>" if sub else "") + "</div></div>")


def sec_title(text, small=""):
    st.html(f'<div class="sec-title">{escape(text)}' + (f" <small>{escape(small)}</small>" if small else "") + "</div>")


def kpi(label, value, unit="", sub="", accent=False):
    return (f'<div class="kpi{" accent" if accent else ""}"><div class="k">{escape(label)}</div>'
            f'<div class="v">{escape(str(value))}<small>{escape(unit)}</small></div>'
            + (f'<div class="s">{escape(sub)}</div>' if sub else "") + "</div>")


def kpi_row(*cards, min_width=None):
    """KPI 카드 한 줄. min_width(px)를 주면 카드가 그 너비까지 좁아질 수 있어 한 줄에 더 많이 놓인다."""
    style = f' style="--kpi-min:{min_width}px"' if min_width else ""
    st.html(f'<div class="kpis"{style}>' + "".join(cards) + "</div>")


def bars(data, unit="", ranked=False, empty="아직 데이터가 없어요."):
    """가로 막대 목록(HTML). data: {이름: 값}"""
    if not data:
        return f'<div class="empty">{escape(empty)}</div>'
    top = max(data.values()) or 1
    rows = "".join(
        f'<div class="bar-row"><span class="n" data-r="{i}">{escape(str(k))}</span>'
        f'<span class="t"><i style="width:{max(v / top * 100, 2):.0f}%"></i></span><span class="c">{(f"{v:,}" if isinstance(v, int) else f"{v:g}")}{unit}</span></div>'
        for i, (k, v) in enumerate(data.items(), 1))
    return f'<div class="bars{" rank-list" if ranked else ""}">{rows}</div>'


def panel(title, hint, body):
    return f'<div class="panel"><h3>{escape(title)}</h3><div class="hint">{escape(hint)}</div>{body}</div>'
