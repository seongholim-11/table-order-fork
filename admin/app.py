"""관리자(OWNER) 페이지: streamlit run admin/app.py --server.port 8502

진입점: 로그인·사이드바 메뉴·화면 선택만 한다. 화면은 admin/views/, 공통 UI 조각은 admin/ui/ 에 있다.
데이터는 모두 admin_repository.py 를 거친다. DATA_SOURCE=dummy|api|auto 로 더미/서버를 바꾼다
(자세한 설명은 admin_repository.py 맨 위). 이 파일에는 데이터 출처에 대한 코드가 없다.
(폴더 이름이 pages 가 아니라 views 인 이유: Streamlit 은 pages/ 폴더를 자동 멀티페이지로 인식한다.)
"""

import importlib
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))  # 저장소 루트: admin.*, shared.* 를 import 하기 위해

import admin_dummy_data  # noqa: E402
import admin_repository as repo_mod  # noqa: E402
import dashboard_stats  # noqa: E402
import marketing_ai  # noqa: E402
import order_filters  # noqa: E402
from admin.marketing import recommendations as marketing_recommendations  # noqa: E402
from admin.views import dashboard as dashboard_view  # noqa: E402
from admin.views import marketing as marketing_view  # noqa: E402
from admin.views import customers as customers_view  # noqa: E402

# 배포 서버가 재시작 없이 새 코드를 받으면 예전 모듈이 메모리에 남아 ImportError 가 난다.
# 상태가 없는 계산 모듈은 매 실행마다 다시 읽는다.
importlib.reload(dashboard_stats)
importlib.reload(order_filters)


def _reload_if_changed(*modules) -> None:
    """저장소·더미 모듈은 파일이 바뀌었거나(또는 이 검사가 없던 옛 프로세스가 올린 것이면) 한 번 다시 읽는다. 의존 순서대로 넘길 것."""
    for m in modules:
        mtime = Path(m.__file__).stat().st_mtime
        if getattr(m, "_loaded_mtime", None) != mtime:
            importlib.reload(m)
            m._loaded_mtime = mtime


# 추천 함수부터 화면 순서로 갱신해, 켜 둔 서버에서도 바뀐 단골 안내가 즉시 반영되게 한다.
_reload_if_changed(admin_dummy_data, marketing_recommendations, marketing_ai, repo_mod, dashboard_view, marketing_view, customers_view)

from admin.views.customers import page_customers  # noqa: E402
from admin.views.calls import page_calls  # noqa: E402
from admin.views.events import page_events  # noqa: E402
from admin.views.dashboard import page_dashboard  # noqa: E402
from admin.views.login import login  # noqa: E402
from admin.views.marketing import page_marketing  # noqa: E402
from admin.views.menu import page_menu  # noqa: E402
from admin.views.orders import page_orders  # noqa: E402
from admin.views.weights import page_weights  # noqa: E402
from admin_repository import DEFAULT_RULE  # noqa: E402

st.set_page_config(page_title="식당도우미 관리자", page_icon="🍺", layout="wide", initial_sidebar_state="auto")
st.html(Path(__file__).with_name("admin.css"))

# 사이드바 메뉴. 화면 안에 탭이 있는 페이지(대시보드·고객 등급·주문 이력·마케팅)는 탭을 접고 펼 수 있는 하위 메뉴로 보여 준다.
SUBPAGES = {
    "대시보드": ["한눈에 보기", "오늘 · 매출", "매출 추이", "고객 분석", "메뉴"],
    "고객 등급": ["고객 목록", "등급 분류 기준"],
    "주문 이력": ["전체 주문", "고객별 주문"],
    "마케팅": ["AI 챗봇", "AI 추천", "AI 문자"],
}
SUBPAGE_ICON = {"대시보드": "📊", "고객 등급": "👥", "주문 이력": "🧾", "마케팅": "💬"}
TOP_PAGES = ["직원 호출", "메뉴 관리", "추천 가중치", "이벤트"]
PAGES = [*TOP_PAGES, *SUBPAGES]
DEFAULT_PAGE = "대시보드"  # 처음 들어오면 보여 줄 화면 (하위 메뉴의 첫 항목이 열린다)
NAV_KEYS = ["nav_top", *(f"nav_sub_{p}" for p in SUBPAGES)]  # 메뉴 묶음마다 라디오 하나 (한 번에 하나만 선택된다)

ss = st.session_state


def _select_nav(key):
    """한 묶음에서 고르면 나머지 묶음의 선택은 지운다."""
    for other in NAV_KEYS:
        if other != key:
            ss[other] = None


ss.setdefault("owner", False)
ss.setdefault("repo", None)
ss.setdefault("notice", None)
ss.setdefault("token", "")
ss.setdefault("menu_editor_v", 0)  # 저장 후 표 편집 상태를 초기화하기 위한 번호
ss.setdefault("menu_cat", st.query_params.get("cat"))  # URL(?cat=)에서 복원 - 메뉴 관리에서 선택한 카테고리 id
ss.setdefault("grade_rule", dict(DEFAULT_RULE))
# 기존 화면을 열어 둔 세션도 새 이름으로 이어서 사용할 수 있게 한다.
if ss.get("nav_sub_대시보드") == "메뉴 · 운영":
    ss["nav_sub_대시보드"] = "메뉴"
if ss["repo"] is not None and type(ss["repo"]) is not repo_mod.AdminRepository:
    ss["owner"], ss["repo"] = False, None  # 코드가 다시 읽히기 전에 만든 옛 저장소 객체는 버리고 다시 입장


if not ss["owner"] and repo_mod.skip_token_login() and not ss.get("auto_login_failed"):
    # 임시: 토큰 입력 없이 입장. 실패하면 아래에서 기존 토큰 입력 화면을 보여준다. (ADMIN_SKIP_TOKEN=0 으로 끔)
    _auto = repo_mod.connect(repo_mod.default_admin_token())
    if _auto.error:
        ss["auto_login_failed"] = True
    else:
        ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, _auto.repo, repo_mod.default_admin_token(), _auto.notice

if not ss["owner"]:
    login()
    st.stop()

repo = ss["repo"]
# 다른 관리자나 서버 재시작으로 저장 기준이 바뀌어도 모든 메뉴에서 최신 값을 반영한다.
# 저장값이 같으면 고객 화면에서 입력하던 미리보기는 유지한다.
current_rule = repo.customer_grade_rules()
if ss.get("customer_rule_defaults") != current_rule or ss.get("customer_rule_source") != repo.source:
    ss["customer_rule_defaults"] = dict(current_rule)
    ss["customer_rule_source"] = repo.source
    customers_view.reset_rule()
    for key in ("ai_candidates", "ai_picked", "sms_excluded"):
        ss.pop(key, None)
# 다른 화면에는 저장 기준만 전달한다. 예전 세션에 남은 복원 미리보기도 여기서 바로잡는다.
ss["grade_rule"] = dict(current_rule)
store = repo.backend.store()
with st.sidebar:
    st.html(f'<div class="sb-brand"><div class="sb-logo">🍺</div><div><div class="sb-name">식당도우미</div>'
            f'<div class="sb-sub">관리자 콘솔</div></div></div><div class="sb-label">MENU</div>')
    # 새로고침해도 보던 메뉴가 유지되도록 URL(?page=...&tab=...)에 저장하고 거기서 복원한다.
    if "nav_top" not in ss:
        url_page = st.query_params["page"] if st.query_params.get("page") in PAGES else DEFAULT_PAGE
        url_tab = st.query_params.get("tab")
        # 예전 북마크로 접근해도 같은 메뉴 화면을 연다.
        if url_page == "대시보드" and url_tab == "메뉴 · 운영":
            url_tab = "메뉴"
        for key in NAV_KEYS:
            ss[key] = None
        if url_page in SUBPAGES:
            ss[f"nav_sub_{url_page}"] = url_tab if url_tab in SUBPAGES[url_page] else SUBPAGES[url_page][0]
        else:
            ss["nav_top"] = url_page
    active_group = next((p for p in SUBPAGES if ss.get(f"nav_sub_{p}")), None)
    # 로그인 직후 가장 중요한 매장 현황을 먼저 찾도록 대시보드를 메뉴 관리보다 위에 둔다.
    dashboard_subs = SUBPAGES["대시보드"]
    with st.expander(f"{SUBPAGE_ICON['대시보드']} 대시보드", expanded=active_group == "대시보드"):
        st.radio("대시보드", dashboard_subs, key="nav_sub_대시보드", index=None, label_visibility="collapsed",
                 on_change=_select_nav, args=("nav_sub_대시보드",))
    st.radio("메뉴", TOP_PAGES, key="nav_top", index=None, label_visibility="collapsed",
             on_change=_select_nav, args=("nav_top",))
    for group, subs in SUBPAGES.items():  # 대시보드 외 하위 메뉴는 기존 순서와 동작을 유지한다.
        if group == "대시보드":
            continue
        with st.expander(f"{SUBPAGE_ICON[group]} {group}", expanded=group == active_group):
            st.radio(group, subs, key=f"nav_sub_{group}", index=None, label_visibility="collapsed",
                     on_change=_select_nav, args=(f"nav_sub_{group}",))
    page = active_group or ss.get("nav_top") or DEFAULT_PAGE
    sub = ss.get(f"nav_sub_{active_group}") if active_group else None
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    if sub and st.query_params.get("tab") != sub:
        st.query_params["tab"] = sub
    st.html('<div style="height:18px"></div><div class="sb-label">STORE</div>')
    st.caption(f"{store['name']} {store['branch']} · OWNER")
    st.caption("🟢 서버 데이터" if repo.source == "api" else "🧪 더미 데이터")
    st.html('<div style="height:10px"></div>')
    if st.button("로그아웃"):
        ss["owner"], ss["repo"] = False, None
        st.rerun()
if ss["notice"]:
    st.warning(ss["notice"])

if page in SUBPAGES:
    {"대시보드": page_dashboard, "고객 등급": page_customers, "주문 이력": page_orders,
     "마케팅": page_marketing}[page](repo, sub)
else:
    {"직원 호출": page_calls, "메뉴 관리": page_menu, "추천 가중치": page_weights, "이벤트": page_events}[page](repo)

# 메뉴 관리에서 고른 카테고리도 URL에 남겨 새로고침 후 복원한다 (페이지 실행 후의 최종 선택값 기준).
if page == "메뉴 관리" and ss["menu_cat"]:
    if st.query_params.get("cat") != ss["menu_cat"]:
        st.query_params["cat"] = ss["menu_cat"]
else:
    st.query_params.pop("cat", None)
if page not in SUBPAGES:
    st.query_params.pop("tab", None)
