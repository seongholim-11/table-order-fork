"""석원 TODO 3: 관리자 화면이 같은 추천 응답 계약을 사용하는지 확인한다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import admin_repository as ar
from admin_dummy_data import DummyBackend


def test_dummy_opportunities_shape_and_round_cycle():
    repo = ar.AdminRepository(DummyBackend())
    first = repo.opportunities(0)
    assert set(first) == {"items", "page", "pages", "summary", "total", "groups"}
    assert set(first["summary"]) == {"members", "orders"}
    assert 1 <= len(first["items"]) <= 4
    assert all({"title", "why", "action", "action_type", "target_grades", "member_ids", "sms_body"} <= set(card)
               for card in first["items"])
    assert first["total"] >= 30  # 1,000명 더미의 생애주기·취향·시간대 조합으로 수십 개를 만든다.
    all_titles = [card["title"] for page in range(first["pages"])
                  for card in repo.opportunities(page)["items"]]
    assert len(all_titles) == first["total"] == len(set(all_titles))
    assert all(len(repo.opportunities(page)["items"]) == 4 for page in range(first["pages"]))
    assert repo.opportunities(first["pages"])["items"] == first["items"]


def test_recommendations_separate_visit_incentives_from_preferences_and_operations():
    repo = ar.AdminRepository(DummyBackend())
    first = repo.opportunities(0)
    titles = {}
    for kind in ("sms", "guide"):
        group = first["groups"][kind]
        cards = [card for page in range(group["pages"])
                 for card in repo.opportunities(page)["groups"][kind]["items"]]
        assert len(cards) == group["total"]
        assert len({card["title"] for card in cards}) == len(cards)
        assert all(card["action_type"] == kind for card in cards)
        assert repo.opportunities(group["pages"])["groups"][kind]["items"] == group["items"]
        titles[kind] = " ".join(card["title"] for card in cards)
        if kind == "sms":
            assert all(card["sms_body"] and card["member_ids"] for card in cards)
        else:
            assert all(not card["sms_body"] for card in cards)
    assert all(title in titles["sms"] for title in ("첫 방문 감사", "세 번째 방문 유도", "휴면 고객 복귀", "생일"))
    assert all(title in titles["guide"] for title in ("매운맛 선호", "순한맛 선호", "선호 고객", "주문 집중 완화"))
    assert not any(title in titles["sms"] for title in ("선호 고객", "반응 실험", "방문 수요 활용"))


def test_empty_recommendation_has_no_sms_and_keeps_the_guide():
    from shared.opportunity_engine import EMPTY_RECOMMENDATION, pick_recommendations

    result = pick_recommendations([dict(EMPTY_RECOMMENDATION)], 3)
    assert result["groups"]["sms"] == {"items": [], "page": 1, "pages": 1, "total": 0}
    assert result["groups"]["guide"]["items"] == [EMPTY_RECOMMENDATION]

